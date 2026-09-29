"""One-time codes in notifications: the notification offers to copy them."""

import re

CODE_WORDS = ("code", "codice", "código", "codigo", "kod", "otp", "pin", "passcode",
              "verification", "verifica", "verify", "one-time", "2fa", "token", "code:",
              "bestätigung", "vérification", "验证码", "認証", "コード", "код", "رمز", "कोड")
CODE = re.compile(r"(?<![\w-])(\d{3}[- ]\d{3}|\d{4,8})(?![\w-])")


def verification_code(summary, body):
    """The one-time code in a notification ("Your code is 482913"), or None.
    Only when the text talks about a code, so prices and dates aren't taken."""
    text = f"{summary}\n{re.sub(r'<[^>]+>', ' ', body or '')}"
    lower = text.lower()
    if not any(word in lower for word in CODE_WORDS):
        return None
    for match in CODE.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        # Not a year or a time.
        if len(digits) == 4 and (1900 <= int(digits) <= 2100):
            continue
        return digits
    return None
