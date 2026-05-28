# DISCLAIMER
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

# RISK
This program reformats the select external device attached to your computer. 
Be aware of the potential loss of data if you select the incorrect device.

# WHY
On Sony cameras, it is recommended that the SD or CFExpress Type A card be
reformatted to prevent database issues before use.  Two challenges with using
the on camera formating:

1. No way to name the SD/CFExpress card
2. If you use display LUTs, you then have to remove from camera, attach to
   computer, and copy LUTs to card.  This is not a good workflow.

This utility formats the card on the PC/MAC and copy the display LUTs onto
the card.  When the card is inserted into the camera, the camera will
automatically build out the remain directory structure and files making it
ready for use.

# APP WINDOW EXAMPLE
[![Application Window](https://github.com/duongk/sony-sd-formatter/blob/main/app_window.png)](https://github.com/duongk/sony-sd-formatter/blob/main/app_window.png)

# VERSIONs

0.1 Beta - Only tested MAC version so far [May 28, 2026]

# COMPILED APPS
I have created a installed image for MAC.  However, I have no way of testing the install on a 
machine that does not already have all the installed packages.  I also do not have a developer 
license to sign the code.  You will need to do a security override if you want use the image
install.

From a terminal.
```bash

xattr -cr
```
# BUILD COMMAND on MAC

Make sure you have all the required Python packages listed in the 'requirements.txt' file.

Run the following command to build the mac bundle:

```bash
python3 -m PyInstaller --noconsole --windowed --clean \
--hidden-import=PySide6 \
--hidden-import=shiboken6 \
--name="Sony Card Formatter" \
--icon=app_icon.icns \
sony_formatter.py

```