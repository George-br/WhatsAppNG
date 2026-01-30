# WhatsApp NG

NVDA add-on that provides accessibility enhancements for the web-based WhatsApp Desktop.

## Features

- **Alt+1**: Go to WhatsApp conversation list
- **Alt+2**: Go to WhatsApp message list
- **Alt+D**: Focus message input field
- **Enter**: Play voice message (works in individual chats and groups)
- **Shift+Enter**: Open message context menu

### Toggle Scripts (no default shortcut - configure in Input Gestures)

- Toggle phone number filtering in conversation list
- Toggle phone number filtering in message list

## Requirements

- NVDA 2021.1 or later
- WhatsApp Desktop (web-based version)

## Installation

1. Download the `whatsAppNG.nvda-addon` file
2. In NVDA, go to **Tools → Add-on Manager**
3. Click **Install** and select the file
4. Restart NVDA

## Configuration

Phone number filters can be toggled:
- In conversation list: Configure a shortcut in Input Gestures
- In message list: Configure a shortcut in Input Gestures

Configure shortcuts in:
**NVDA menu → Preferences → Input Gestures → WhatsApp NG**

## Credits

Developed by Nuno Costa to provide accessibility enhancements for the modern WhatsApp Desktop experience.

## Support

For issues or suggestions, please visit:
https://github.com/nrfcosta21/whatsAppNG/issues

## Translation Compilation

To compile the `.po` file and generate the `.mo` file:

1. Install GNU Gettext:
   - Windows: http://gnuwin32.sourceforge.net/downlinks/gettext.php
   - Copy `msgfmt.exe` to the add-on folder

2. Compile the translation:
   ```bash
   msgfmt locale/pt_BR/LC_MESSAGES/nvda.po -o locale/pt_BR/LC_MESSAGES/nvda.mo
   ```

3. Or use Python:
   ```bash
   python -m pip install polib
   python -c "import polib; po = polib.pofile('locale/pt_BR/LC_MESSAGES/nvda.po'); po.save_as_mofile('locale/pt_BR/LC_MESSAGES/nvda.mo')"
   ```
