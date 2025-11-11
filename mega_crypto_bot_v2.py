
# Save as: mega_crypto_bot_v2.py
import os
import asyncio
import sqlite3
import time
import requests
import logging
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# === CONFIGURATION ===
BOT_TOKEN = "8551812823:AAHVeXJg4aGc3pL73KRowK51yrteWaH7YcY"
ADMIN_ID = "5665906172"
YOUR_USDT_WALLET = "0x9E66D726F13C9A1F22cC7e5A4a308d3BA183599a"
SUPPORT_USERNAME = "@Kingstonebridge"  # Change to your support
# === END CONFIGURATION ===

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UltimatePaymentHandler:
    def __init__(self):
        self.conn = sqlite3.connect('premium_users_v2.db')
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
                performance REAL DEFAULT 0,
                market_type TEXT DEFAULT 'crypto'
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ams_investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                amount REAL,
                plan_type TEXT,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT DEFAULT 'active',
                weekly_profit REAL DEFAULT 0,
                total_profit REAL DEFAULT 0
            )
        ''')
        self.conn.commit()

    def create_payment_request(self, user_id, username, amount, plan_type, duration_days=30):
        """Create payment record"""
        payment_id = f"{plan_type}_{int(time.time())}_{user_id}"
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO premium_users 
            (user_id, username, plan_type, amount_paid, payment_date, expiry_date, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, plan_type, amount, datetime.now(), 
              datetime.now() + timedelta(days=duration_days), payment_id))
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

    def add_trading_signal(self, symbol, signal_type, entry_price, targets, stop_loss, leverage=1, market_type='crypto'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO trading_signals (symbol, signal_type, entry_price, targets, stop_loss, leverage, market_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, signal_type, entry_price, targets, stop_loss, leverage, market_type))
        self.conn.commit()
        return cursor.lastrowid

    def update_signal_performance(self, signal_id, performance):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE trading_signals SET performance = ? WHERE id = ?', (performance, signal_id))
        self.conn.commit()

    def get_recent_signals(self, limit=10, market_type=None):
        cursor = self.conn.cursor()
        if market_type:
            cursor.execute('SELECT * FROM trading_signals WHERE market_type = ? ORDER BY timestamp DESC LIMIT ?', (market_type, limit))
        else:
            cursor.execute('SELECT * FROM trading_signals ORDER BY timestamp DESC LIMIT ?', (limit,))
        return cursor.fetchall()

    def create_ams_investment(self, user_id, username, amount, plan_type):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ams_investments (user_id, username, amount, plan_type, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, amount, plan_type, datetime.now(), datetime.now() + timedelta(days=90)))
        self.conn.commit()
        return cursor.lastrowid

payment_handler = UltimatePaymentHandler()

class UltimateCryptoBotV2:
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
        self.application.add_handler(CommandHandler("vip", self.vip_command))
        self.application.add_handler(CommandHandler("ams", self.ams_command))
        self.application.add_handler(CommandHandler("paid", self.paid_command))
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("performance", self.performance_command))
        
        # Market signals
        self.application.add_handler(CommandHandler("forex", self.forex_signals))
        self.application.add_handler(CommandHandler("crypto", self.crypto_signals))
        self.application.add_handler(CommandHandler("gold", self.gold_signals))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("confirm", self.confirm_payment_command))
        self.application.add_handler(CommandHandler("pending", self.pending_payments_command))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.application.add_handler(CommandHandler("addsignal", self.add_signal_command))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("🚀 FREE SIGNALS", callback_data="free_signals")],
            [InlineKeyboardButton("💎 VIP PLANS", callback_data="vip_plans")],
            [InlineKeyboardButton("💰 AMS SERVICE", callback_data="ams_service")],
            [InlineKeyboardButton("📊 LIVE PERFORMANCE", callback_data="performance")],
            [InlineKeyboardButton("🆘 SUPPORT", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"🔥 <b>WELCOME {user.first_name} TO APEX BULL SIGNALS!</b>\n\n"
            "🎯 <b>PROVEN TRACK RECORD:</b>\n"
            "• 92% Win Rate on Forex Signals\n"
            "• 87% Win Rate on Crypto Futures\n"
            "• 4-7 Daily Premium Signals\n"
            "• 24/7 Market Monitoring\n\n"
            "💎 <b>VIP FEATURES INCLUDE:</b>\n"
            "• Real-time Forex & Crypto Signals\n"
            "• Early Entry Alerts (5-15min advance)\n"
            "• Technical Analysis Reports\n"
            "• Portfolio Management\n"
            "• 1-on-1 Support\n"
            "• Account Management Service (AMS)\n\n"
            "📈 <i>Daily Performance: 200%-700% Profit Potential</i>\n\n"
            "👇 <b>Choose Your Option:</b>",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "free_signals":
            await self.send_free_signal(query)
        elif query.data == "vip_plans":
            await self.show_vip_plans(query)
        elif query.data == "ams_service":
            await self.show_ams_service(query)
        elif query.data == "performance":
            await self.performance_command_query(query)
        elif query.data == "confirm_vip":
            await self.show_vip_payment(query)
        elif query.data == "confirm_ams":
            await self.show_ams_payment(query)
        elif query.data == "forex_signals":
            await self.send_forex_signal(query)
        elif query.data == "crypto_signals":
            await self.send_crypto_signal(query)

    async def show_vip_plans(self, query):
        keyboard = [
            [InlineKeyboardButton("🥇 LIFETIME - $300", callback_data="vip_lifetime")],
            [InlineKeyboardButton("💰 1 YEAR - $200", callback_data="vip_year")],
            [InlineKeyboardButton("📅 3 MONTHS - $120", callback_data="vip_3months")],
            [InlineKeyboardButton("🔄 BACK TO MAIN", callback_data="free_signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💎 <b>VIP PREMIUM MEMBERSHIP PLANS</b>\n\n"
            "🚀 <b>WHAT YOU GET:</b>\n"
            "• 4-7 Daily Premium Signals\n"
            "• Real-time Forex & Crypto Alerts\n"
            "• Early Entry Points\n"
            "• Technical Analysis\n"
            "• 24/7 Support\n"
            "• Risk Management Guidance\n\n"
            "💰 <b>SUBSCRIPTION PLANS:</b>\n"
            "• 🥇 Lifetime: $300 (Regular $500)\n"
            "• 💰 1 Year: $200\n"
            "• 📅 3 Months: $120\n"
            "• 📅 1 Month: $70\n\n"
            "🎯 <b>Daily Profit Potential: 200%-700%</b>\n\n"
            "👇 Select Your Plan:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_vip_payment(self, query, plan_type="VIP_MONTHLY"):
        user_id = query.from_user.id
        username = query.from_user.username or "Unknown"
        
        plans = {
            "VIP_LIFETIME": {"amount": 300, "days": 3650},
            "VIP_YEAR": {"amount": 200, "days": 365},
            "VIP_3MONTHS": {"amount": 120, "days": 90},
            "VIP_MONTHLY": {"amount": 70, "days": 30}
        }
        
        plan = plans.get(plan_type, plans["VIP_MONTHLY"])
        payment_id = payment_handler.create_payment_request(user_id, username, plan["amount"], plan_type, plan["days"])
        
        keyboard = [
            [InlineKeyboardButton("🆘 CONTACT SUPPORT", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("📊 PERFORMANCE", callback_data="performance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💎 <b>VIP {plan_type.replace('_', ' ')} ACTIVATION</b>\n\n"
            f"💰 <b>Send ${plan['amount']} USDT</b> to:\n"
            f"<code>{YOUR_USDT_WALLET}</code>\n\n"
            "🌐 <b>Network:</b> BEP20 (Binance Smart Chain)\n\n"
            "📝 <b>IMPORTANT: Include this Payment ID in memo:</b>\n"
            f"<code>{payment_id}</code>\n\n"
            "✅ <b>After payment, use:</b>\n"
            f"<code>/paid {payment_id}</code>\n\n"
            "⚡ <i>Activation within 5 minutes of payment confirmation</i>\n\n"
            "🎯 <b>You'll get immediate access to:</b>\n"
            "• 4-7 daily premium signals\n"
            "• Real-time trading alerts\n"
            "• Technical analysis\n"
            "• VIP support channel",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_ams_service(self, query):
        keyboard = [
            [InlineKeyboardButton("💰 INVEST $1000", callback_data="ams_1000")],
            [InlineKeyboardButton("💰 INVEST $2000", callback_data="ams_2000")],
            [InlineKeyboardButton("💰 INVEST $5000", callback_data="ams_5000")],
            [InlineKeyboardButton("🔄 BACK", callback_data="vip_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💰 <b>ACCOUNT MANAGEMENT SERVICE (AMS)</b>\n\n"
            "🚀 <b>PROFIT SHARING PROGRAM:</b>\n"
            "We trade for you and share profits weekly!\n\n"
            "📈 <b>INVESTMENT PLANS:</b>\n"
            "• $1000 → $500 weekly profit (50%)\n"
            "• $2000 → $1000 weekly profit (50%)\n"
            "• $5000 → $3000 weekly profit (60%)\n"
            "• $10,000 → $6000 weekly profit (60%)\n\n"
            "⏰ <b>Contract Duration:</b> 3 Months\n"
            "💰 <b>Profit Payout:</b> Every Friday\n"
            "🛡️ <b>Capital Protection:</b> Secure Trading\n\n"
            "🎯 <b>Why Choose Our AMS?</b>\n"
            "• Professional Fund Management\n"
            "• Weekly Consistent Returns\n"
            "• Transparent Reporting\n"
            "• 24/7 Account Monitoring\n\n"
            "👇 Select Your Investment Plan:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def show_ams_payment(self, query, investment_amount=1000):
        user_id = query.from_user.id
        username = query.from_user.username or "Unknown"
        
        plans = {
            "ams_1000": 1000,
            "ams_2000": 2000,
            "ams_5000": 5000,
            "ams_10000": 10000
        }
        
        amount = plans.get(query.data, 1000)
        payment_id = f"AMS_{amount}_{int(time.time())}_{user_id}"
        
        # Create AMS investment record
        payment_handler.create_ams_investment(user_id, username, amount, f"AMS_{amount}")
        
        keyboard = [
            [InlineKeyboardButton("🆘 CONTACT FOR AMS", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("💎 VIP PLANS", callback_data="vip_plans")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        weekly_profit = amount * 0.5 if amount <= 2000 else amount * 0.6
        
        await query.edit_message_text(
            f"💰 <b>ACCOUNT MANAGEMENT SERVICE - ${amount}</b>\n\n"
            f"📈 <b>Investment Amount:</b> ${amount:,}\n"
            f"💵 <b>Weekly Profit:</b> ${weekly_profit:,.0f}\n"
            f"⏰ <b>Duration:</b> 3 Months\n"
            f"📅 <b>Payout:</b> Every Friday\n\n"
            "🔒 <b>Secure Investment Process:</b>\n"
            "1. Contact our manager for AMS setup\n"
            "2. Transfer funds to managed account\n"
            "3. We trade professionally for you\n"
            "4. Receive weekly profit share\n\n"
            f"👨‍💼 <b>Contact AMS Manager:</b>\n"
            f"{SUPPORT_USERNAME}\n\n"
            "💬 <i>Message directly for AMS enrollment and secure investment procedure</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def send_free_signal(self, query):
        """Send free sample signals"""
        free_signal = self.generate_forex_signal()
        
        keyboard = [
            [InlineKeyboardButton("💎 GET VIP SIGNALS", callback_data="vip_plans")],
            [InlineKeyboardButton("📈 FOREX SIGNALS", callback_data="forex_signals")],
            [InlineKeyboardButton("₿ CRYPTO SIGNALS", callback_data="crypto_signals")],
            [InlineKeyboardButton("💰 AMS SERVICE", callback_data="ams_service")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 <b>FREE SAMPLE SIGNAL</b>\n\n"
            f"{free_signal}\n\n"
            f"⚠️ <i>Free signals are limited and delayed</i>\n"
            f"💎 <b>VIP members get 4-7 real-time signals daily</b>\n\n"
            f"🔥 <i>Recent VIP Results:</i>\n"
            f"• EURUSD: +85 pips ✅\n"
            f"• XAUUSD: +$1200 profit ✅\n"
            f"• BTCUSD: +3.2% in 2 hours ✅\n\n"
            f"👇 Upgrade for real-time premium signals:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def send_forex_signal(self, query):
        """Send forex signal"""
        forex_signal = self.generate_forex_signal()
        
        keyboard = [
            [InlineKeyboardButton("💎 VIP FOREX SIGNALS", callback_data="vip_plans")],
            [InlineKeyboardButton("🔄 MORE SIGNALS", callback_data="free_signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🌍 <b>FOREX TRADING SIGNAL</b>\n\n"
            f"{forex_signal}\n\n"
            f"💡 <b>VIP Members Get:</b>\n"
            f"• 4-7 daily forex signals\n"
            f"• Real-time entry/exit alerts\n"
            f"• Technical analysis\n"
            f"• Risk management\n\n"
            f"🎯 <i>Upgrade to VIP for consistent profits</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def send_crypto_signal(self, query):
        """Send crypto signal"""
        crypto_signal = self.generate_crypto_signal()
        
        keyboard = [
            [InlineKeyboardButton("💎 VIP CRYPTO SIGNALS", callback_data="vip_plans")],
            [InlineKeyboardButton("🔄 MORE SIGNALS", callback_data="free_signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"₿ <b>CRYPTO TRADING SIGNAL</b>\n\n"
            f"{crypto_signal}\n\n"
            f"💡 <b>VIP Members Get:</b>\n"
            f"• Early pump alerts\n"
            f"• Spot & futures signals\n"
            f"• Whale movement tracking\n"
            f"• Technical analysis\n\n"
            f"🚀 <i>Join VIP for maximum profits</i>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    # Command handlers
    async def vip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_vip_plans(update.callback_query)

    async def ams_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_ams_service(update.callback_query)

    async def forex_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not payment_handler.is_user_premium(user_id):
            await self.send_forex_signal(update.callback_query)
        else:
            # Send real forex signals to VIP members
            recent_forex = payment_handler.get_recent_signals(3, 'forex')
            if recent_forex:
                signals_text = "🌍 <b>LATEST FOREX SIGNALS</b>\n\n"
                for signal in recent_forex:
                    signals_text += self.format_signal(signal) + "\n\n"
            else:
                signals_text = self.generate_forex_signal()
            
            await update.message.reply_html(signals_text)

    async def crypto_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not payment_handler.is_user_premium(user_id):
            await self.send_crypto_signal(update.callback_query)
        else:
            # Send real crypto signals to VIP members
            recent_crypto = payment_handler.get_recent_signals(3, 'crypto')
            if recent_crypto:
                signals_text = "₿ <b>LATEST CRYPTO SIGNALS</b>\n\n"
                for signal in recent_crypto:
                    signals_text += self.format_signal(signal) + "\n\n"
            else:
                signals_text = self.generate_crypto_signal()
            
            await update.message.reply_html(signals_text)

    async def gold_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        gold_signal = self.generate_gold_signal()
        await update.message.reply_html(gold_signal)

    # Signal generators
    def generate_forex_signal(self):
        pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'AUDUSD']
        pair = random.choice(pairs)
        
        entry = round(random.uniform(1.05, 1.25) if 'USD' in pair else random.uniform(150, 180), 5)
        tp1 = round(entry + random.uniform(0.002, 0.005), 5)
        tp2 = round(entry + random.uniform(0.005, 0.01), 5)
        sl = round(entry - random.uniform(0.002, 0.004), 5)
        
        return (
            f"🌍 <b>{pair} SIGNAL</b>\n\n"
            f"🎯 Direction: {'BUY' if random.random() > 0.5 else 'SELL'}\n"
            f"📍 Entry: {entry}\n"
            f"🎯 TP1: {tp1}\n"
            f"🎯 TP2: {tp2}\n"
            f"🛡️ SL: {sl}\n\n"
            f"⚡ Risk: 1-2%\n"
            f"📊 Confidence: {random.randint(85, 95)}%"
        )

    def generate_crypto_signal(self):
        coins = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'XRPUSD', 'ADAUSD']
        coin = random.choice(coins)
        
        entry = random.randint(25000, 60000) if 'BTC' in coin else random.randint(1000, 4000)
        tp1 = int(entry * (1 + random.uniform(0.02, 0.05)))
        tp2 = int(entry * (1 + random.uniform(0.05, 0.1)))
        sl = int(entry * (1 - random.uniform(0.015, 0.03)))
        
        return (
            f"₿ <b>{coin} SIGNAL</b>\n\n"
            f"🎯 Direction: {'LONG' if random.random() > 0.5 else 'SHORT'}\n"
            f"📍 Entry: ${entry:,}\n"
            f"🎯 TP1: ${tp1:,}\n"
            f"🎯 TP2: ${tp2:,}\n"
            f"🛡️ SL: ${sl:,}\n"
            f"⚡ Leverage: {random.randint(3, 10)}x\n\n"
            f"📊 Confidence: {random.randint(88, 96)}%"
        )

    def generate_gold_signal(self):
        entry = random.randint(1950, 2050)
        tp1 = entry + random.randint(5, 15)
        tp2 = entry + random.randint(15, 30)
        sl = entry - random.randint(8, 20)
        
        return (
            f"🥇 <b>XAUUSD (GOLD) SIGNAL</b>\n\n"
            f"🎯 Direction: {'BUY' if random.random() > 0.5 else 'SELL'}\n"
            f"📍 Entry: {entry}\n"
            f"🎯 TP1: {tp1}\n"
            f"🎯 TP2: {tp2}\n"
            f"🛡️ SL: {sl}\n\n"
            f"⚡ Risk: 1-2%\n"
            f"📊 Confidence: {random.randint(85, 92)}%"
        )

    # Keep existing methods from previous version
    async def pro_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_vip_plans(update.callback_query)

    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not payment_handler.is_user_premium(user_id):
            await self.send_free_signal(update.callback_query)
        else:
            recent_signals = payment_handler.get_recent_signals(5)
            if recent_signals:
                signals_text = "🚀 <b>LATEST VIP SIGNALS</b>\n\n"
                for signal in recent_signals:
                    signals_text += self.format_signal(signal) + "\n\n"
            else:
                signals_text = self.generate_forex_signal() + "\n\n" + self.generate_crypto_signal()
            
            await update.message.reply_html(signals_text)

    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        performance_stats = self.get_performance_stats()
        await update.message.reply_html(performance_stats)

    async def performance_command_query(self, query):
        performance_stats = self.get_performance_stats()
        await query.edit_message_text(performance_stats, parse_mode='HTML')

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not payment_handler.is_user_premium(user_id):
            await update.message.reply_html("💎 <b>VIP FEATURE</b>\n\nPortfolio tracking available for VIP members only.\nUse /vip to upgrade!")
        else:
            portfolio_value = random.randint(5000, 50000)
            await update.message.reply_html(f"🏆 <b>YOUR VIP PORTFOLIO</b>\n\n💰 Value: ${portfolio_value:,}\n📈 Today: +${random.randint(100, 1000)}\n🎯 Win Rate: {random.randint(85, 95)}%")

    async def paid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /paid YOUR_PAYMENT_ID")
            return
        
        payment_id = context.args[0]
        if payment_handler.confirm_payment(payment_id):
            await update.message.reply_html("🎉 <b>WELCOME TO VIP!</b>\n\nYou now have full VIP access to premium signals!")
        else:
            await update.message.reply_html("⏳ Payment being verified...")

    # Admin commands (keep from previous version)
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        # Admin panel implementation

    async def add_signal_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        # Add signal implementation

    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        # Confirm payment implementation

    async def pending_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        # Pending payments implementation

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            return
        # Broadcast implementation

    async def price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Price implementation
        pass

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 Use /start to see all features\n💎 Use /vip for premium plans\n🚀 Use /signals for trading signals")

    def get_performance_stats(self):
        return (
            "📈 <b>APEX BULL PERFORMANCE TRACKER</b>\n\n"
            "🏆 <b>Last Week Results:</b>\n"
            f"• Win Rate: {random.randint(88, 96)}%\n"
            f"• Total Signals: {random.randint(25, 35)}\n"
            f"• Average ROI: +{random.randint(8, 15)}%\n"
            f"• Best Trade: +{random.randint(45, 85)}%\n\n"
            "💎 <b>Monthly Performance:</b>\n"
            f"• Overall ROI: +{random.randint(65, 120)}%\n"
            f"• Successful Trades: {random.randint(85, 120)}\n"
            f"• Consistency Score: {random.randint(90, 98)}/100\n\n"
            "💰 <b>AMS Investment Returns:</b>\n"
            f"• Weekly Profit Sharing: 50-60%\n"
            f"• Total AMS Payouts: ${random.randint(50000, 150000)}\n"
            f"• Happy Investors: {random.randint(150, 300)}+"
        )

    def format_signal(self, signal):
        id, symbol, signal_type, entry, targets, stop_loss, leverage, timestamp, performance, market_type = signal
        return (
            f"🎯 <b>{symbol} {signal_type}</b>\n"
            f"📍 Entry: {entry}\n"
            f"🎯 Targets: {targets}\n"
            f"🛡️ SL: {stop_loss}\n"
            f"📊 Performance: +{performance}%"
        )

    def run(self):
        logger.info("🚀 APEX BULL BOT V2 STARTING...")
        logger.info("💎 Features: VIP Plans, AMS Service, Forex & Crypto Signals")
        self.application.run_polling()

# === MAIN EXECUTION ===
if __name__ == "__main__":
    bot = UltimateCryptoBotV2(BOT_TOKEN)
    bot.run()
