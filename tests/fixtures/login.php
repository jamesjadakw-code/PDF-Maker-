<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Log in · BAM CRM</title>
<style>
@import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap");
:root{--bg:#0a0a0a;--surface:#111111;--border:#2e2e2e;--text:#f5f5f5;--muted:#a3a3a3;--accent:#ffc107;--font:"Source Sans 3","Segoe UI",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px}
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.login-card{width:100%;max-width:400px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:28px}
.login-card img{width:190px;border-radius:6px;margin:0 auto 14px;display:block;background:#222;height:80px}
.side-brand{color:var(--accent);font-weight:900;letter-spacing:.04em;font-size:15px;text-align:center}
.side-motto{background:var(--accent);color:#111;font-weight:900;font-size:11px;text-align:center;padding:9px 8px;border-radius:6px;margin:10px 0 18px;letter-spacing:.02em}
.f{display:flex;flex-direction:column;gap:4px}
.mb{margin-bottom:12px}
label{font-size:12px;color:var(--muted)}
input{background:#0a0a0a;border:1px solid var(--border);color:#fff;border-radius:8px;padding:10px}
.btn{display:inline-block;border:1px solid #333;background:#171717;color:#fff;border-radius:8px;padding:11px 14px;font-weight:700}
.btn-y{background:var(--accent);color:#111;border-color:var(--accent)}
.hint{font-size:11.5px;color:var(--muted)}
.mt{margin-top:12px}
a{color:var(--accent)}
</style>
</head>
<body><div class="login-wrap"><form class="login-card" method="post" autocomplete="on">
<div style="width:190px;height:80px;margin:0 auto 14px;background:#1a1a1a;border-radius:6px"></div>
<div class="side-brand">BIG ASS MOTORS · CRM</div><div class="side-motto">YOU CAN'T DEPOSIT EXCUSES</div>
<input type="hidden" name="_csrf" value="test-csrf"><input type="hidden" name="next" value="">
<div class="f mb"><label>E-mail</label><input type="email" name="email" required autofocus value=""></div>
<div class="f mb"><label>Password</label><input type="password" name="password" required></div>
<button class="btn btn-y" style="width:100%">Log in</button>
<p class="hint mt" style="text-align:center"><a href="https://bigassmotors.com/">← bigassmotors.com</a></p>
</form></div></body></html>
