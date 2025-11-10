# templates/otp_email.py
def otp_email_html(otp: str, user_name: str | None = None) -> str:
    name = user_name or "there"
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:auto;">
      <h2>Verify your login</h2>
      <p>Hi {name},</p>
      <p>Your one-time password (OTP) is:</p>
      <div style="font-size:28px;font-weight:700;letter-spacing:4px;margin:16px 0;">{otp}</div>
      <p>This code will expire in <strong>3 minutes</strong>. If you didn’t request it, you can ignore this email.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
      <p style="color:#666;font-size:12px;">Do not share this code with anyone.</p>
    </div>
    """

def otp_email_text(otp: str, user_name: str | None = None) -> str:
    name = user_name or "there"
    return f"""Verify your login

Hi {name},
Your OTP is: {otp}
It expires in 3 minutes. If you didn’t request it, ignore this email.
"""
