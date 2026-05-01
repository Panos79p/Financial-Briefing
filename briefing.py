import os
import re
import json
import datetime
import smtplib
import anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
EMAIL_SENDER      = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD    = os.environ["EMAIL_PASSWORD"]
EMAIL_RECIPIENT   = os.environ["EMAIL_RECIPIENT"]
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def gather_market_data():
    print("Searching for market data...")

    today = datetime.date.today().strftime("%d %B %Y")

    prompt = f"""Today is {today}. Search the web and find current values for:
S&P500, Nasdaq, Brent crude, Gold, 10Y Treasury, VIX, Bitcoin, EUR/USD — including today's price, daily % change, and year-to-date % change.
Also find the top 4 financial news stories this week.

Return ONLY valid JSON, no explanation, no markdown, no extra text. Use this exact structure:

{{"week_date":"{today}","tickers":{{"sp500":{{"price":"7,200","change_pct":"+0.5","ytd_pct":"+4.0"}},"nasdaq":{{"price":"24,800","change_pct":"+0.3","ytd_pct":"+5.0"}},"brent":{{"price":"110.00","change_pct":"-1.0","ytd_pct":"+80"}},"ust10y":{{"price":"4.40","ytd_note":"Fed on hold"}},"gold":{{"price":"4,600","change_pct":"+0.5","ytd_pct":"+38"}}}},"macro":{{"fed_rate":{{"value":"3.50%","note":"On hold","context":"Powell last FOMC"}},"vix":{{"value":"18.00","change_pct":"-2.0","ytd_pct":"+20","label":"Below 20 · Calm"}},"bitcoin":{{"price":"76,000","change_pct":"+1.0","ytd_pct":"-19"}},"eurusd":{{"rate":"1.1700","change_pct":"-0.2","ytd_pct":"-0.2"}}}},"stories":[{{"tag":"Fed / Rates","tag_color":"#185FA5","headline":"Headline here","body":"2-3 sentence summary."}},{{"tag":"Energy / Geopolitics","tag_color":"#D85A30","headline":"Headline here","body":"2-3 sentence summary."}},{{"tag":"Tech / AI","tag_color":"#533AB7","headline":"Headline here","body":"2-3 sentence summary."}},{{"tag":"Earnings","tag_color":"#1D9E75","headline":"Headline here","body":"2-3 sentence summary."}}],"watch_text":"2-3 sentence summary of the week.","sources":"CNBC, Reuters, Yahoo Finance"}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            result_text += block.text

    print("Raw response received, extracting JSON...")

    # Try ```json block first
    match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
    if match:
        return json.loads(match.group(1).strip())

    # Try raw JSON object
    match = re.search(r'\{[\s\S]*\}', result_text)
    if match:
        return json.loads(match.group(0).strip())

    raise ValueError(f"No JSON found in response:\n{result_text}")


def build_html_email(data):

    def color(pct, invert=False):
        try:
            v = float(str(pct).replace("%","").replace("+",""))
            if invert:
                return "#D85A30" if v > 0 else "#1D9E75"
            return "#1D9E75" if v > 0 else "#D85A30"
        except:
            return "#888888"

    def ytd(pct):
        try:
            v = float(str(pct).replace("%","").replace("+","").strip())
            return f"YTD {'+' if v>0 else ''}{v:.1f}%"
        except:
            return str(pct)

    t  = data.get("tickers", {})
    m  = data.get("macro", {})
    st = data.get("stories", [])

    stories_html = ""
    for i, s in enumerate(st):
        border = "border-top:1px solid #e5e7eb;padding-top:14px;margin-top:14px;" if i > 0 else ""
        stories_html += f"""<div style="{border}padding-left:14px;border-left:3px solid #e5e7eb;">
<div style="font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;font-family:monospace;color:{s.get('tag_color','#666')};margin-bottom:4px;">{s.get('tag','')}</div>
<div style="font-family:Georgia,serif;font-size:15px;font-weight:700;color:#111827;margin:0 0 5px;line-height:1.35;">{s.get('headline','')}</div>
<div style="font-size:13px;color:#1f2937;line-height:1.65;">{s.get('body','')}</div>
</div>"""

    week_date = data.get("week_date", datetime.date.today().strftime("%d %B %Y"))
    watch     = data.get("watch_text", "")
    sources   = data.get("sources", "CNBC, Reuters, Yahoo Finance")

    sp  = t.get("sp500",  {})
    nas = t.get("nasdaq", {})
    br  = t.get("brent",  {})
    ust = t.get("ust10y", {})
    go  = t.get("gold",   {})
    fed = m.get("fed_rate", {})
    vix = m.get("vix",      {})
    btc = m.get("bitcoin",  {})
    eur = m.get("eurusd",   {})

    vix_mood = vix.get("label","").split("·")[1].strip() if "·" in vix.get("label","") else "—"

    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>Weekly Financial Briefing</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,0.08);max-width:640px;width:100%;">

<tr><td style="padding:28px 32px 20px;border-bottom:2px solid #111827;">
<table width="100%"><tr>
<td><div style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#111827;">Weekly Financial Briefing</div>
<div style="font-size:12px;color:#9ca3af;margin-top:5px;font-family:monospace;">Week of {week_date}</div></td>
<td align="right"><div style="font-size:11px;color:#9ca3af;font-family:monospace;">COMPILED FRIDAYS</div></td>
</tr></table></td></tr>

<tr><td style="padding:20px 32px 0;">
<div style="font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#9ca3af;margin-bottom:10px;font-family:monospace;">Markets at a glance</div>
<table width="100%"><tr>
<td width="19%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:10px;color:#9ca3af;font-family:monospace;">S&amp;P 500</div>
<div style="font-size:16px;font-weight:500;color:#111827;margin:3px 0;">{sp.get("price","—")}</div>
<div style="font-size:11px;font-family:monospace;color:#666;">{sp.get("change_pct","—")}%</div>
<div style="font-size:10px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(sp.get('ytd_pct','0'))}">{ytd(sp.get('ytd_pct',''))}</div>
</td><td width="2%"></td>
<td width="19%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:10px;color:#9ca3af;font-family:monospace;">NASDAQ</div>
<div style="font-size:16px;font-weight:500;color:#111827;margin:3px 0;">{nas.get("price","—")}</div>
<div style="font-size:11px;font-family:monospace;color:#666;">{nas.get("change_pct","—")}%</div>
<div style="font-size:10px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(nas.get('ytd_pct','0'))}">{ytd(nas.get('ytd_pct',''))}</div>
</td><td width="2%"></td>
<td width="19%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:10px;color:#9ca3af;font-family:monospace;">BRENT</div>
<div style="font-size:16px;font-weight:500;color:#111827;margin:3px 0;">${br.get("price","—")}</div>
<div style="font-size:11px;font-family:monospace;color:#666;">{br.get("change_pct","—")}%</div>
<div style="font-size:10px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(br.get('ytd_pct','0'))}">{ytd(br.get('ytd_pct',''))}</div>
</td><td width="2%"></td>
<td width="19%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:10px;color:#9ca3af;font-family:monospace;">10Y UST</div>
<div style="font-size:16px;font-weight:500;color:#111827;margin:3px 0;">{ust.get("price","—")}%</div>
<div style="font-size:11px;font-family:monospace;color:#9ca3af;">+1bp</div>
<div style="font-size:10px;font-family:monospace;font-weight:500;margin-top:3px;color:#1f2937;">{ust.get("ytd_note","—")}</div>
</td><td width="2%"></td>
<td width="19%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:10px;color:#BA7517;font-family:monospace;">GOLD</div>
<div style="font-size:16px;font-weight:500;color:#BA7517;margin:3px 0;">${go.get("price","—")}</div>
<div style="font-size:11px;font-family:monospace;color:#666;">{go.get("change_pct","—")}%</div>
<div style="font-size:10px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(go.get('ytd_pct','0'))}">{ytd(go.get('ytd_pct',''))}</div>
</td>
</tr></table></td></tr>

<tr><td style="padding:20px 32px 0;">
<div style="font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#9ca3af;margin-bottom:10px;font-family:monospace;">Macro snapshot</div>
<table width="100%"><tr>
<td width="23%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:11px;color:#1f2937;font-family:monospace;margin-bottom:3px;">Fed funds rate</div>
<div style="font-size:18px;font-weight:500;color:#111827;">{fed.get("value","—")}</div>
<div style="font-size:11px;color:#1f2937;margin-top:2px;">{fed.get("note","—")}</div>
<div style="font-size:11px;font-family:monospace;font-weight:500;margin-top:3px;color:#1f2937;">{fed.get("context","—")}</div>
</td><td width="2%"></td>
<td width="23%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:11px;color:#1f2937;font-family:monospace;margin-bottom:3px;">VIX · Fear Index</div>
<div style="font-size:18px;font-weight:500;color:#111827;">{vix.get("value","—")}</div>
<div style="font-size:11px;color:#1f2937;margin-top:2px;">{vix.get("change_pct","—")}% today</div>
<div style="font-size:11px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(vix.get('ytd_pct','0'), invert=True)};">YTD {vix.get("ytd_pct","—")}% · {vix_mood}</div>
</td><td width="2%"></td>
<td width="23%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:11px;color:#1f2937;font-family:monospace;margin-bottom:3px;">Bitcoin</div>
<div style="font-size:18px;font-weight:500;color:#111827;">${btc.get("price","—")}</div>
<div style="font-size:11px;color:#1f2937;margin-top:2px;">{btc.get("change_pct","—")}% today</div>
<div style="font-size:11px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(btc.get('ytd_pct','0'))};">YTD {btc.get("ytd_pct","—")}%</div>
</td><td width="2%"></td>
<td width="23%" style="background:#f9fafb;border-radius:8px;padding:10px;border:1px solid #e5e7eb;vertical-align:top;">
<div style="font-size:11px;color:#185FA5;font-family:monospace;margin-bottom:3px;">EUR / USD</div>
<div style="font-size:18px;font-weight:500;color:#111827;">{eur.get("rate","—")}</div>
<div style="font-size:11px;color:#1f2937;margin-top:2px;">{eur.get("change_pct","—")}% today</div>
<div style="font-size:11px;font-family:monospace;font-weight:600;margin-top:3px;color:{color(eur.get('ytd_pct','0'))};">YTD {eur.get("ytd_pct","—")}%</div>
</td>
</tr></table></td></tr>

<tr><td style="padding:20px 32px 0;"><hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"></td></tr>

<tr><td style="padding:16px 32px 0;">
<div style="font-size:10px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#9ca3af;margin-bottom:14px;font-family:monospace;">Top stories</div>
{stories_html}
</td></tr>

<tr><td style="padding:20px 32px;">
<div style="background:#f9fafb;border-radius:8px;padding:14px 16px;border-left:4px solid #BA7517;">
<div style="font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#BA7517;font-family:monospace;margin-bottom:6px;">Watch this week</div>
<div style="font-size:13px;color:#111827;line-height:1.65;">{watch}</div>
</div></td></tr>

<tr><td style="padding:0 32px 24px;">
<hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 12px;">
<table width="100%"><tr>
<td style="font-size:11px;color:#9ca3af;font-family:monospace;">Sources: {sources}</td>
<td align="right" style="font-size:11px;color:#9ca3af;font-family:monospace;">Auto-generated every Friday</td>
</tr></table></td></tr>

</table></td></tr></table>
</body></html>"""


def send_email(html_content, week_date):
    print(f"Sending email to {EMAIL_RECIPIENT}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Weekly Financial Briefing — {week_date}"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
    print("✅ Email sent successfully.")


def main():
    print(f"Starting Weekly Financial Briefing — {datetime.date.today()}")
    data      = gather_market_data()
    html      = build_html_email(data)
    week_date = data.get("week_date", datetime.date.today().strftime("%d %B %Y"))
    send_email(html, week_date)
    print("Done.")


if __name__ == "__main__":
    main()
