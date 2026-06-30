import os
import sys
import logging
import io
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
def get_token():
    """Get bot token from environment variables."""
    token = os.environ.get('BOT_TOKEN')
    if not token:
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ No BOT_TOKEN found in environment variables!")
        logger.error("Please add BOT_TOKEN to your Railway Variables.")
        sys.exit(1)
    return token

TOKEN = get_token()
logger.info("✅ Bot token loaded successfully!")

# Store user's image data
user_images = {}

# Flip options
FLIP_OPTIONS = {
    'horizontal': '↔️ Flip Horizontal (Mirror)',
    'vertical': '↕️ Flip Vertical (Upside Down)',
    'both': '🔄 Flip Both (180° Rotation)'
}

# Helper Functions
def build_flip_keyboard() -> InlineKeyboardMarkup:
    """Builds an inline keyboard for flip options."""
    keyboard = [
        [
            InlineKeyboardButton(FLIP_OPTIONS['horizontal'], callback_data="flip_horizontal"),
            InlineKeyboardButton(FLIP_OPTIONS['vertical'], callback_data="flip_vertical"),
        ],
        [
            InlineKeyboardButton(FLIP_OPTIONS['both'], callback_data="flip_both"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="flip_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def flip_image(image_data: bytes, flip_type: str) -> bytes:
    """Flip image using Pillow."""
    try:
        img = Image.open(io.BytesIO(image_data))
        
        if flip_type == 'horizontal':
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif flip_type == 'vertical':
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif flip_type == 'both':
            img = img.transpose(Image.ROTATE_180)
        else:
            raise ValueError("Invalid flip type")
        
        output_buffer = io.BytesIO()
        img.save(output_buffer, format='PNG')
        return output_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Flip error: {e}")
        raise e

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message."""
    user = update.effective_user
    welcome_text = f"""
🔄 **Welcome to PixFlipbot, {user.first_name}!**

I flip images horizontally, vertically, or both!

**How to use:**
1️⃣ Send me an image
2️⃣ Choose how you want to flip it
3️⃣ Get your flipped image back!

**Commands:**
/start - Show this welcome message
/help - Show all commands
/flip - Flip an image (send one first)

💡 **Tip:** You can flip any image format (JPG, PNG, WebP, etc.)!
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    help_text = """
📖 **How to use PixFlipbot:**

1️⃣ Send me any image
2️⃣ Choose from the buttons:
   • Flip Horizontal (Mirror)
   • Flip Vertical (Upside Down)
   • Flip Both (180° Rotation)
3️⃣ Get your flipped image back!

**Commands:**
/start - Welcome message
/help - Show this help message
/flip - Flip an image (send one first)

**Supported formats:**
JPG, PNG, WebP, GIF, BMP, and more!

💡 **Pro tip:** Send multiple images to flip them one by one!
"""
    await update.message.reply_text(help_text)

async def flip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /flip command."""
    user_id = update.effective_user.id
    
    if user_id in user_images and user_images[user_id]:
        keyboard = build_flip_keyboard()
        await update.message.reply_text(
            "🔄 **Choose how to flip your image:**",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "❌ Please send me an image first!\n\n"
            "Send an image, then use /flip or tap the buttons."
        )

# Callback Handler for Buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles flip selection from inline buttons."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "flip_cancel":
        await query.edit_message_text("❌ Flip cancelled. Send a new image to try again.")
        user_images.pop(user_id, None)
        return
    
    # Get the user's image
    image_data = user_images.get(user_id)
    if not image_data:
        await query.edit_message_text("❌ Please send an image first!")
        return
    
    # Extract flip type
    flip_type = data.replace("flip_", "")
    flip_name = FLIP_OPTIONS.get(flip_type, flip_type)
    
    try:
        # Show processing
        await query.edit_message_text(f"🔄 Flipping image {flip_name}...")
        
        # Flip the image
        flipped_data = await flip_image(image_data, flip_type)
        
        # Send the flipped image back
        await update.effective_chat.send_document(
            document=io.BytesIO(flipped_data),
            filename=f"flipped_{flip_type}.png",
            caption=f"✅ **Image flipped successfully!**\n\n"
                    f"🔄 Flip type: {flip_name}"
        )
        
        await query.edit_message_text("🎉 Done! Send another image to flip it.")
        user_images.pop(user_id, None)  # Clear state after successful flip
        
    except Exception as e:
        logger.error(f"Flip failed for user {user_id}: {e}")
        await query.edit_message_text(
            f"❌ Sorry, I couldn't flip this image.\n\n"
            f"Error: {str(e)}\n\n"
            f"💡 Try sending a different image."
        )

# Message Handlers
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles when a user sends a photo."""
    user_id = update.effective_user.id
    photo_file = await update.message.photo[-1].get_file()
    image_data = await photo_file.download_as_bytearray()
    
    user_images[user_id] = image_data
    
    keyboard = build_flip_keyboard()
    await update.message.reply_text(
        "🖼️ **Image received!**\n\n"
        "Choose how you want to flip it:",
        reply_markup=keyboard
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles when a user sends a document (file)."""
    document = update.message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        user_id = update.effective_user.id
        file = await document.get_file()
        image_data = await file.download_as_bytearray()
        
        user_images[user_id] = image_data
        
        keyboard = build_flip_keyboard()
        await update.message.reply_text(
            "🖼️ **Image received!**\n\n"
            "Choose how you want to flip it:",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "📎 Please send an image file (JPG, PNG, WebP, etc.)."
        )

# Main Function
def main() -> None:
    """Start the bot."""
    try:
        # Create Application
        application = Application.builder().token(TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("flip", flip_command))
        
        # Add callback handler for inline buttons
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Add message handlers
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
        
        # Handle text messages (not commands)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                              lambda u, c: u.message.reply_text(
                                                  "📤 Please send me an image to flip!\n"
                                                  "Use /help for more information."
                                              )))
        
        # Start the Bot
        logger.info("🚀 PixFlipbot started successfully!")
        logger.info("🔄 Press Ctrl+C to stop.")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
