"""
emailer.py - sends an email through YOUR email account (Lesson 26).

It uses SMTP, the standard way programs send email. Your login details live in .env
(private, never uploaded). For Gmail you need an "App Password" - a separate 16-letter
password just for this program - NOT your normal Gmail password:
  Google Account -> Security -> 2-Step Verification (must be on) -> App passwords

.env settings:
  EMAIL_TO=you@example.com          who receives the report
  SMTP_USER=you@gmail.com           the account that sends it
  SMTP_PASSWORD=abcdefghijklmnop    the App Password (no spaces)
  SMTP_HOST=smtp.gmail.com          (optional, Gmail is the default)
  SMTP_PORT=465                     (optional)

Check your settings, or resend a saved email:
  python -m lab.emailer --test
  python -m lab.emailer --resend data/paper_bot_email.html
"""

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

import certifi
from dotenv import load_dotenv

load_dotenv()


def email_settings():
    settings = {
        "to": os.getenv("EMAIL_TO"),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "465")),
    }
    missing = [k for k in ("to", "user", "password") if not settings[k]]
    if missing:
        raise SystemExit("Email isn't set up yet: add EMAIL_TO, SMTP_USER and SMTP_PASSWORD "
                         "to your .env file (see emailer.py for how).")
    password = settings["password"].replace(" ", "")
    if "gmail" in settings["host"] and not (len(password) == 16 and password.isalpha()):
        print("Warning: a Gmail App Password is exactly 16 letters. Yours isn't - it may be your "
              "normal password, which Gmail refuses. See emailer.py for how to create one.")
    settings["password"] = password  # Google shows it as 'abcd efgh ijkl mnop'; spaces are optional
    return settings


class EmailError(Exception):
    """Sending failed - with a plain-English explanation."""


def send_email(subject, html_body, settings=None, smtp_class=smtplib.SMTP_SSL):
    """
    Send one HTML email. `smtp_class` can be swapped for a fake one in tests,
    so the tests never send real email.
    """
    settings = settings or email_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["user"]
    message["To"] = settings["to"]
    message.set_content("Your email app can't show HTML. Open data/daily_report.html instead.")
    message.add_alternative(html_body, subtype="html")  # the nice version

    # SSL = an encrypted connection, so nobody in between can read your password
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with smtp_class(settings["host"], settings["port"], context=context) as server:
            server.login(settings["user"], settings["password"])
            server.send_message(message)
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected) as error:
        raise EmailError("The email server refused the login. For Gmail, SMTP_PASSWORD must be a "
                         f"16-letter App Password, not your normal password. ({error})") from error
    except (smtplib.SMTPException, OSError) as error:
        raise EmailError(f"Couldn't send the email: {error}") from error


if __name__ == "__main__":  # only runs when you start THIS file directly
    if "--test" in sys.argv:
        send_email("Test from stock-market-data-lab", "<p>Your email settings work.</p>")
        print("Test email sent - check your inbox.")
    elif "--resend" in sys.argv:
        path = sys.argv[sys.argv.index("--resend") + 1]
        with open(path) as f:
            send_email(f"Resent: {os.path.basename(path)}", f.read())
        print(f"Sent {path}.")
    else:
        print(__doc__)
