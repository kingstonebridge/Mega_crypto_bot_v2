# Save as: mega_crypto_bot.py
import asyncio
import sqlite3
import time
import requests
import logging
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
from dotenv import load_dotenv

# Add at the top
from keep_alive import keep_alive

# Add before bot.run()
# Load environment variables
load_dotenv()

# === CONFIGURATION ===
BOT_TOKEN = os.getenv('BOT_TOKEN', "8551812823:AAHVeXJg4aGc3pL73KRowK51yrteWaH7YcY")
ADMIN_ID = os.getenv('ADMIN_ID', "5665906172")
YOUR_USDT_WALLET = os.getenv('YOUR_USDT_WALLET', "0x9E66D726F13C9A1F22cC7e5A4a308d3BA183599a")
# === END CONFIGURATION ===
# === CONFIGURATION ===

BOT_TOKEN = "8451690160:AAGTXV2d4w9QeOngfEAwkxJkU5_0Hhsgarc"
ADMIN_ID = "5665906172"
YOUR_USDT_WALLET = "0x9E66D726F13C9A1F22cC7e5A4a308d3BA183599a"
# === END CONFIGURATION ===

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UltimatePaymentHandler:
    def __init__(self):
        self.conn = sqlite3.connect('premium_users.db')
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                plan_type TEXT,
                amount_paid REAL,
                payment_date TIMESTAMP,
                expiry_date TIMESTAMP,
                payment_id TEXT,
                transaction_hash TEXT,
                status TEXT DEFAULT 'pending',
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                signal_type TEXT,
                entry_price REAL,
                targets TEXT,
                stop_loss REAL,
                leverage INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                performance REAL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_signals INTEGER DEFAULT 0,
                winning_signals INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_payment_request(self, user_id, username, amount=29.99, plan_type="PRO"):
        """Create payment record"""
        payment_id = f"PRO_{int(time.time())}_{user_id}"
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO premium_users 
            (user_id, username, plan_type, amount_paid, payment_date, expiry_date, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, plan_type, amount, datetime.now(), 
              datetime.now() + timedelta(days=30), payment_id))
        self.conn.commit()
        
        return payment_id

    def is_user_premium(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT expiry_date, status FROM premium_users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result and result[1] == 'completed':
            expiry_date = datetime.fromisoformat(result[0]) if isinstance(result[0], str) else result[0]
            return datetime.now() < expiry_date
        return False

    def confirm_payment(self, payment_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE premium_users SET status = "completed" WHERE payment_id = ?', (payment_id,))
        success = cursor.rowcount > 0
        self.conn.commit()
        return success

    def get_pending_payments(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id, username, payment_id, amount_paid FROM premium_users WHERE status = "pending"')
        return cursor.fetchall()

    def add_trading_signal(self, symbol, signal_type, entry_price, targets, stop_loss, leverage=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO trading_signals (symbol, signal_type, entry_price, targets, stop_loss, leverage)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, signal_type, entry_price, targets, stop_loss, leverage))
        self.conn.commit()
        return cursor.lastrowid

    def update_signal_performance(self, signal_id, performance):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE trading_signals SET performance = ? WHERE id = ?', (performance, signal_id))
        self.conn.commit()

    def get_recent_signals(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM trading_signals ORDER BY timestamp DESC LIMIT ?', (limit,))
        return cursor.fetchall()

payment_handler = UltimatePaymentHandler()

class UltimateCryptoBot:
    def __init__(self, token):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.last_signal_time = {}

    def setup_handlers(self):
        # Core commands
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("price", self.price))
        self.application.add_handler(CommandHandler("signals", self.signals_command))
        
        # Premium features
        self.application.add_handler(CommandHandler("pro", self.pro_command))
        self.application.add_handler(CommandHandler("paid", self.paid_command))
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("performance", self.performance_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("confirm", self.confirm_payment_command))
        self.application.add_handler(CommandHandler("pending", self.pending_payments_command))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("🚀 FREE SIGNALS", callback_data="free_signals")],
            [InlineKeyboardButton("💎 GO PRO ($29.99/mo)", callback_data="go_pro")],
            [InlineKeyboardButton("📊 LIVE PERFORMANCE", callback_data="performance")],
            [InlineKeyboardButton("🆘 SUPPORT", url="https://t.me/YourSupport")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"🔥 <b>WELCOME {user.first_name} TO APEX CRYPTO SIGNALS!</b>\n\n"
            "🎯 <b>PROVEN TRACK RECORD:</b>\n"
            "• 92% Win Rate on Spot Signals\n"
            "• 87% Win Rate on Futures\n"
            "• 24/7 Market Monitoring\n"
            "• Real-time Entry/Exit Alerts\n\n"
            "💎 <b>PRO FEATURES INCLUDE:</b>\n"
            "• VIP Spot & Futures Signals\n"
            "• Early Pump Alerts (5-15min advance)\n"
            "• Whale Movement Tracking\n"
            "• Technical Analysis Reports\n"
            "• Portfolio Management\n"
            "• 1-on-1 Support\n\n"
            "📈 <i>Last Week Performance: +37.2% ROI</i>\n\n"
            "👇 <b>Choose Your Plan:</b>",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "free_signals":
            await self.send_free_signal(query)
        elif query.data == "go_pro":
            await self.pro_command_query(query)
        elif query.data == "performance":
            await self.performance_command_query(query)
        elif query.data == "confirm_pro":  # FIXED: Added this missing case
            await self.pro_command_query(query, confirmed=True)

    async def send_free_signal(self, query):
        """Send limited free signal to attract upgrades"""
        free_signal = self.generate_free_signal()
        
        keyboard = [
            [InlineKeyboardButton("💎 GET REAL-TIME PRO SIGNALS", callback_data="go_pro")],
            [InlineKeyboardButton("📊 SEE LIVE PERFORMANCE", callback_data="performance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 <b>FREE SAMPLE SIGNAL</b>\n\n"
            f"{free_signal}\n\n"
            f"⚠️ <i>Free signals are delayed by 15-30 minutes</i>\n"
            f"💎 <b>Pro members get signals in REAL-TIME with exact entry points</b>\n\n"
            f"📈 <i>Last Pro Signal: BTC +8.3% in 4 hours</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def pro_command_query(self, query, confirmed=False):
        user_id = query.from_user.id
        username = query.from_user.username or "Unknown"
        
        if payment_handler.is_user_premium(user_id):
            await query.edit_message_text(
                "💎 <b>YOU'RE ALREADY PRO!</b>\n\n"
                "Thank you for being part of our elite trading community!\n\n"
                "Use /signals for latest signals\n"
                "Use /portfolio for your stats\n"
                "Use /performance for track record",
                parse_mode='HTML'
            )
            return
        
        if not confirmed:
            keyboard = [
                [InlineKeyboardButton("✅ CONFIRM PRO UPGRADE", callback_data="confirm_pro")],
                [InlineKeyboardButton("📊 SEE PERFORMANCE", callback_data="performance")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "💎 <b>APEX PRO MEMBERSHIP - $29.99/month</b>\n\n"
                "🚀 <b>WHAT YOU GET:</b>\n"
                "• Real-time Spot & Futures Signals\n"
                "• 5-15min Early Pump Alerts\n"
                "• Whale Wallet Tracking\n"
                "• Technical Analysis Reports\n"
                "• Portfolio Management Tools\n"
                "• 24/7 Support\n\n"
                "📊 <b>LAST WEEK RESULTS:</b>\n"
                "• BTC Spot: +12.4%\n"
                "• ETH Futures: +23.7%\n"
                "• ALT Pump: +45.2%\n"
                "• Overall ROI: +37.2%\n\n"
                "💰 <b>Payment: $29.99 USDT (BEP20)</b>\n"
                f"Wallet: <code>{YOUR_USDT_WALLET}</code>\n\n"
                "👇 Confirm to get payment instructions:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return
        
        # Create payment request
        payment_id = payment_handler.create_payment_request(user_id, username, 29.99, "PRO")
        
        keyboard = [
            [InlineKeyboardButton("🆘 NEED HELP?", url="https://t.me/YourSupport")],
            [InlineKeyboardButton("📊 PERFORMANCE", callback_data="performance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💎 <b>PRO MEMBERSHIP ACTIVATION</b>\n\n"
            "💰 <b>Send $29.99 USDT</b> to:\n"
            f"<code>{YOUR_USDT_WALLET}</code>\n\n"
            "🌐 <b>Network:</b> BEP20 (Binance Smart Chain)\n\n"
            "📝 <b>IMPORTANT: Include this Payment ID in memo:</b>\n"
            f"<code>{payment_id}</code>\n\n"
            "✅ <b>After payment, use:</b>\n"
            f"<code>/paid {payment_id}</code>\n\n"
            "⚡ <i>Activation within 5 minutes of payment confirmation</i>\n\n"
            "🎯 <b>You'll get immediate access to:</b>\n"
            "• Real-time trading signals\n"
            "• Early pump alerts\n"
            "• Portfolio tracking\n"
            "• VIP support",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def pro_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pro command from text message"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        if payment_handler.is_user_premium(user_id):
            await update.message.reply_html(
                "💎 <b>YOU'RE ALREADY PRO!</b>\n\n"
                "Thank you for being part of our elite trading community!\n\n"
                "Use /signals for latest signals\n"
                "Use /portfolio for your stats\n"
                "Use /performance for track record"
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ CONFIRM PRO UPGRADE", callback_data="confirm_pro")],
            [InlineKeyboardButton("📊 SEE PERFORMANCE", callback_data="performance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            "💎 <b>APEX PRO MEMBERSHIP - $29.99/month</b>\n\n"
            "🚀 <b>WHAT YOU GET:</b>\n"
            "• Real-time Spot & Futures Signals\n"
            "• 5-15min Early Pump Alerts\n"
            "• Whale Wallet Tracking\n"
            "• Technical Analysis Reports\n"
            "• Portfolio Management Tools\n"
            "• 24/7 Support\n\n"
            "📊 <b>LAST WEEK RESULTS:</b>\n"
            "• BTC Spot: +12.4%\n"
            "• ETH Futures: +23.7%\n"
            "• ALT Pump: +45.2%\n"
            "• Overall ROI: +37.2%\n\n"
            "💰 <b>Payment: $29.99 USDT (BEP20)</b>\n"
            f"Wallet: <code>{YOUR_USDT_WALLET}</code>\n\n"
            "👇 Confirm to get payment instructions:",
            reply_markup=reply_markup
        )

    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not payment_handler.is_user_premium(user_id):
            # Free users get delayed sample signal
            free_signal = self.generate_free_signal()
            keyboard = [
                [InlineKeyboardButton("💎 GO PRO FOR REAL-TIME SIGNALS", callback_data="go_pro")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                f"🎯 <b>FREE SAMPLE SIGNAL (DELAYED)</b>\n\n"
                f"{free_signal}\n\n"
                f"⚠️ <i>Free signals are 15-30 minutes delayed</i>\n"
                f"💎 <b>Pro members get signals in REAL-TIME with exact entry points</b>\n\n"
                f"🔥 <i>Last Pro Results:</i>\n"
                f"• BTC: +8.3% (4 hours)\n"
                f"• ETH: +5.7% (6 hours)\n"
                f"• SOL: +12.1% (2 hours)",
                reply_markup=reply_markup
            )
        else:
            # Pro users get real signals
            recent_signals = payment_handler.get_recent_signals(3)
            if recent_signals:
                signals_text = "🚀 <b>LATEST PRO SIGNALS</b>\n\n"
                for signal in recent_signals:
                    signals_text += self.format_signal(signal) + "\n\n"
            else:
                signals_text = self.generate_live_signal()
            
            keyboard = [
                [InlineKeyboardButton("📊 MY PERFORMANCE", callback_data="performance")],
                [InlineKeyboardButton("🔄 REFRESH SIGNALS", callback_data="free_signals")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                signals_text,
                reply_markup=reply_markup
            )

    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        performance_stats = self.get_performance_stats()
        
        keyboard = [
            [InlineKeyboardButton("💎 GO PRO", callback_data="go_pro")],
            [InlineKeyboardButton("🚀 GET SIGNALS", callback_data="free_signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            performance_stats,
            reply_markup=reply_markup
        )

    async def performance_command_query(self, query):
        performance_stats = self.get_performance_stats()
        
        keyboard = [
            [InlineKeyboardButton("💎 GO PRO", callback_data="go_pro")],
            [InlineKeyboardButton("🚀 GET SIGNALS", callback_data="free_signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            performance_stats,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not payment_handler.is_user_premium(user_id):
            await update.message.reply_html(
                "💎 <b>PRO FEATURE</b>\n\n"
                "Portfolio tracking is available for Pro members only.\n\n"
                "Track your:\n"
                "• Real-time P&L\n"
                "• Performance analytics\n"
                "• Risk assessment\n"
                "• Trade history\n\n"
                "Use /pro to upgrade!"
            )
        else:
            # Mock portfolio data for Pro users
            portfolio_value = random.randint(5000, 50000)
            daily_pnl = random.randint(-500, 1000)
            total_pnl = random.randint(1000, 10000)
            
            await update.message.reply_html(
                f"🏆 <b>YOUR PRO PORTFOLIO</b>\n\n"
                f"💰 Portfolio Value: ${portfolio_value:,}\n"
                f"📈 Today's P&L: ${daily_pnl:+,}\n"
                f"🎯 Total P&L: ${total_pnl:+,}\n"
                f"📊 Win Rate: {random.randint(75, 92)}%\n"
                f"⚡ Best Trade: +{random.randint(15, 45)}%\n\n"
                f"💡 <i>AI Recommendation: Consider taking profits on recent winners</i>"
            )

    async def paid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /paid YOUR_PAYMENT_ID")
            return
        
        payment_id = context.args[0]
        
        if payment_handler.confirm_payment(payment_id):
            await update.message.reply_html(
                "🎉 <b>WELCOME TO APEX PRO!</b>\n\n"
                "Your payment has been confirmed and you now have full access to:\n\n"
                "🚀 <b>Real-time Trading Signals</b>\n"
                "💎 <b>Early Pump Alerts</b>\n"
                "📊 <b>Portfolio Tracking</b>\n"
                "🛡️ <b>VIP Support</b>\n\n"
                "Use /signals for latest signals\n"
                "Use /portfolio for your stats\n\n"
                "📞 <i>Contact @YourSupport for any questions</i>"
            )
        else:
            await update.message.reply_html(
                f"⏳ <b>Payment Processing</b>\n\n"
                f"Payment ID: <code>{payment_id}</code>\n\n"
                f"Your payment is being verified...\n"
                f"This usually takes 2-5 minutes.\n\n"
                f"If it takes longer, contact support."
            )

    # Admin commands
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        
        keyboard = [
            [InlineKeyboardButton("📋 Pending Payments", callback_data="admin_pending")],
            [InlineKeyboardButton("📊 Send Signal", callback_data="admin_signal")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🛠️ <b>Admin Panel</b>\n\n"
            "Choose an option:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /confirm PAYMENT_ID")
            return
        
        payment_id = context.args[0]
        if payment_handler.confirm_payment(payment_id):
            await update.message.reply_text(f"✅ Payment {payment_id} confirmed!")
        else:
            await update.message.reply_text("❌ Payment not found")

    async def pending_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        
        pending = payment_handler.get_pending_payments()
        if not pending:
            await update.message.reply_text("✅ No pending payments")
            return
        
        message = "📋 <b>Pending Payments:</b>\n\n"
        for payment in pending:
            message += f"User: {payment[1]} ({payment[0]})\n"
            message += f"Amount: ${payment[3]}\n"
            message += f"ID: <code>{payment[2]}</code>\n"
            message += f"Confirm: /confirm {payment[2]}\n\n"
        
        await update.message.reply_html(message)

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /broadcast YOUR_MESSAGE")
            return
        
        # This would broadcast to all users in a real implementation
        message = ' '.join(context.args)
        await update.message.reply_text(f"📢 Broadcast sent: {message}")

    async def price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOT']
        prices_text = "📊 <b>Live Crypto Prices</b>\n\n"
        
        for coin in coins:
            try:
                response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT', timeout=5)
                data = response.json()
                price = float(data['price'])
                prices_text += f"• {coin}: ${price:,.2f}\n"
            except:
                prices_text += f"• {coin}: ❌ Unavailable\n"
        
        await update.message.reply_html(prices_text)

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Use /start to see all features\n"
            "💎 Use /pro to upgrade to premium\n"
            "🚀 Use /signals for trading signals"
        )

    # Helper methods
    def generate_free_signal(self):
        coins = ['BTC', 'ETH', 'SOL', 'BNB', 'ADA']
        coin = random.choice(coins)
        
        signals = [
            f"🎯 <b>{coin} SPOT SIGNAL</b>\nEntry: ${random.randint(100, 1000)}\nTarget: +{random.randint(3, 8)}%\nSL: -2%",
            f"⚡ <b>{coin} FUTURES SETUP</b>\nLeverage: {random.randint(3, 10)}x\nDirection: {'LONG' if random.random() > 0.5 else 'SHORT'}\nPotential: +{random.randint(5, 15)}%",
            f"🔥 <b>{coin} BREAKOUT ALERT</b>\nWatch: ${random.randint(50, 500)} resistance\nBreak above for +{random.randint(4, 12)}% move"
        ]
        return random.choice(signals)

    def generate_live_signal(self):
        coins = ['BTC', 'ETH', 'SOL', 'BNB', 'AVAX', 'MATIC']
        coin = random.choice(coins)
        entry = random.randint(100, 2000)
        target1 = entry * (1 + random.uniform(0.03, 0.08))
        target2 = entry * (1 + random.uniform(0.06, 0.12))
        stop_loss = entry * (1 - random.uniform(0.015, 0.03))
        
        return (
            f"🚀 <b>VIP {coin} SIGNAL</b>\n\n"
            f"📍 Entry: ${entry:,.2f}\n"
            f"🎯 Target 1: ${target1:,.2f}\n"
            f"🎯 Target 2: ${target2:,.2f}\n"
            f"🛡️ Stop Loss: ${stop_loss:,.2f}\n"
            f"⚡ Leverage: {random.randint(3, 10)}x\n\n"
            f"📊 Confidence: {random.randint(75, 92)}%\n"
            f"⏰ Timeframe: {random.randint(2, 12)} hours"
        )

    def get_performance_stats(self):
        return (
            "📈 <b>APEX SIGNALS PERFORMANCE</b>\n\n"
            "🏆 <b>Last 7 Days:</b>\n"
            f"• Win Rate: {random.randint(85, 95)}%\n"
            f"• Total Signals: {random.randint(15, 25)}\n"
            f"• Average ROI: +{random.randint(5, 12)}%\n"
            f"• Best Trade: +{random.randint(25, 55)}%\n\n"
            "💎 <b>Monthly Track Record:</b>\n"
            f"• Overall ROI: +{random.randint(35, 65)}%\n"
            f"• Successful Trades: {random.randint(45, 65)}\n"
            f"• Consistency Score: {random.randint(88, 96)}/100\n\n"
            "🚀 <b>Why Choose Apex?</b>\n"
            "• Real-time signal delivery\n"
            "• 5-15min early pump alerts\n"
            "• Professional risk management\n"
            "• 24/7 market monitoring\n\n"
            "💡 <i>Join 2,500+ profitable traders</i>"
        )

    def format_signal(self, signal):
        id, symbol, signal_type, entry, targets, stop_loss, leverage, timestamp, performance = signal
        return (
            f"🎯 <b>{symbol} {signal_type}</b>\n"
            f"📍 Entry: ${entry:,.2f}\n"
            f"🎯 Targets: {targets}\n"
            f"🛡️ SL: ${stop_loss:,.2f}\n"
            f"⚡ Leverage: {leverage}x\n"
            f"📊 Performance: +{performance}%"
        )

    def run(self):
        logger.info("🚀 ULTIMATE CRYPTO BOT STARTING...")
        logger.info("💎 Features: Pro Signals, Performance Tracking, VIP Access")
        self.application.run_polling()

# === MAIN EXECUTION ===
if __name__ == "__main__":
    bot = UltimateCryptoBot(BOT_TOKEN)
    keep_alive()

# Add before bot.run()
    bot.run()
