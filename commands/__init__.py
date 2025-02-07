from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

# this has to run before we import the command handlers
filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)
