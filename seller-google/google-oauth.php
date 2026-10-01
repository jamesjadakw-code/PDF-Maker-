<?php
/**
 * Big Ass Motors Exclusive Sellers — Google sign-in + Gmail link helpers.
 * Drop these files into public_html/seller/ next to login.php.
 */

function bam_google_config(): array
{
    static $cfg = null;
    if ($cfg !== null) {
        return $cfg;
    }
    $path = __DIR__ . '/google-config.php';
    $example = __DIR__ . '/google-config.example.php';
    $cfg = is_file($path) ? require $path : (is_file($example) ? require $example : []);
    $cfg += [
        'client_id' => '',
        'client_secret' => '',
        'redirect_uri' => bam_google_default_redirect(),
        'allowed_domains' => [],
        'allowed_emails' => [],
        'allow_any_google' => true,
        'session_name' => 'BAMSESS',
        'portal' => 'seller',
        'home_after_login' => 'index.php',
        'mock_google' => false,
        'scopes' => [
            'openid',
            'email',
            'profile',
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
        ],
    ];
    return $cfg;
}

function bam_google_default_redirect(): string
{
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || ((int) ($_SERVER['SERVER_PORT'] ?? 80) === 443);
    $host = $_SERVER['HTTP_HOST'] ?? 'www.bigassmotors.com';
    $base = ($https ? 'https://' : 'http://') . $host;
    $dir = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/seller/google-callback.php')), '/');
    if ($dir === '/' || $dir === '\\') {
        $dir = '';
    }
    return $base . $dir . '/google-callback.php';
}

function bam_google_configured(): bool
{
    $cfg = bam_google_config();
    if (!empty($cfg['mock_google'])) {
        return true;
    }
    $id = (string) $cfg['client_id'];
    $secret = (string) $cfg['client_secret'];
    return $id !== '' && !str_contains($id, 'YOUR_GOOGLE')
        && $secret !== '' && !str_contains($secret, 'YOUR_GOOGLE');
}

function bam_google_allowed(string $email): bool
{
    $email = strtolower(trim($email));
    if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        return false;
    }
    $cfg = bam_google_config();
    if (!empty($cfg['allow_any_google'])) {
        return true;
    }
    foreach ($cfg['allowed_emails'] as $allowed) {
        if (strtolower(trim($allowed)) === $email) {
            return true;
        }
    }
    $domain = substr(strrchr($email, '@') ?: '', 1);
    foreach ($cfg['allowed_domains'] as $allowedDomain) {
        if (strtolower(trim($allowedDomain)) === $domain) {
            return true;
        }
    }
    return false;
}

function bam_google_start_session(): void
{
    $name = bam_google_config()['session_name'] ?: 'BAMSESS';
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_name($name);
        $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
            || ((int) ($_SERVER['SERVER_PORT'] ?? 80) === 443);
        session_set_cookie_params([
            'lifetime' => 0,
            'path' => '/',
            'secure' => $secure,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        session_start();
    }
}

function bam_google_oauth_url(string $state, ?string $redirectUri = null): string
{
    $cfg = bam_google_config();
    $params = [
        'client_id' => $cfg['client_id'],
        'redirect_uri' => $redirectUri ?: $cfg['redirect_uri'],
        'response_type' => 'code',
        'scope' => implode(' ', $cfg['scopes']),
        'state' => $state,
        'access_type' => 'offline',
        'include_granted_scopes' => 'true',
        'prompt' => 'consent',
    ];
    return 'https://accounts.google.com/o/oauth2/v2/auth?' . http_build_query($params);
}

function bam_google_button_html(): string
{
    $href = 'google-start.php';
    return <<<HTML
<style id="bam-google-login-css">
.bam-google-login{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;background:#fff;color:#1f1f1f;border:1px solid #747775;border-radius:8px;padding:11px 12px;font-weight:700;text-decoration:none;margin:4px 0 2px}
.bam-google-login:hover{background:#f7f8f8;border-color:#747775;color:#1f1f1f}
.bam-google-or{display:flex;align-items:center;gap:10px;margin:14px 0 10px;color:#737373;font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.bam-google-or:before,.bam-google-or:after{content:"";flex:1;height:1px;background:#d5d5d5}
.bam-gmail-note{text-align:center;font-size:11px;color:#666;margin:0 0 14px}
</style>
<a class="bam-google-login" href="{$href}">
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 12 24 12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.6 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.5-5.2l-6.2-5.2C29.3 35.9 26.8 37 24 37c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1.1 3.2-3.5 5.8-6.6 7.3l6.2 5.2C38.3 37.3 44 31.5 44 24c0-1.2-.1-2.3-.4-3.5z"/></svg>
  Continue with Google
</a>
<p class="bam-gmail-note">Signs you into Exclusive Sellers and links this Gmail inbox.</p>
<div class="bam-google-or">or</div>
HTML;
}

function bam_google_inject_button(string $html): string
{
    if (str_contains($html, 'bam-google-login')) {
        return $html;
    }
    $btn = bam_google_button_html();
    $injected = preg_replace(
        '/(<form[^>]*method="post"[^>]*>\s*<input type="hidden" name="_csrf"[^>]*>)/i',
        '$1' . $btn,
        $html,
        1,
        $count
    );
    if ($count > 0) {
        return $injected;
    }
    $injected = preg_replace(
        '/(<button[^>]*class="[^"]*btn-yellow[^"]*"[^>]*>)/i',
        $btn . '$1',
        $html,
        1,
        $count
    );
    if ($count > 0) {
        return $injected;
    }
    return preg_replace('/<\/form>/i', $btn . '</form>', $html, 1) ?? $html;
}

function bam_google_detect_session_keys(string $phpSource): array
{
    preg_match_all('/\$_SESSION\[\s*[\'"]([a-zA-Z0-9_]+)[\'"]\s*\]\s*=/', $phpSource, $m);
    return array_values(array_unique($m[1] ?? []));
}

function bam_google_read_nearby_php(): string
{
    $src = '';
    $skip = [
        'google-oauth.php', 'google-login-wrap.php', 'google-start.php',
        'google-callback.php', 'google-gmail.php', 'google-config.php',
        'google-config.example.php',
    ];
    foreach (glob(__DIR__ . '/*.php') ?: [] as $file) {
        if (in_array(basename($file), $skip, true)) {
            continue;
        }
        $src .= file_get_contents($file) ?: '';
    }
    foreach (['inc', 'includes', 'lib', 'app', 'src'] as $dir) {
        foreach (glob(__DIR__ . '/' . $dir . '/*.php') ?: [] as $file) {
            $src .= file_get_contents($file) ?: '';
        }
        foreach (glob(dirname(__DIR__) . '/' . $dir . '/*.php') ?: [] as $file) {
            $src .= file_get_contents($file) ?: '';
        }
    }
    return $src;
}

function bam_google_bridge_session(array $profile, array $tokens = []): void
{
    bam_google_start_session();
    $email = strtolower(trim((string) ($profile['email'] ?? '')));
    $name = trim((string) ($profile['name'] ?? $email));
    $user = [
        'id' => $profile['id'] ?? $profile['sub'] ?? substr(hash('sha256', $email), 0, 16),
        'email' => $email,
        'name' => $name,
        'role' => 'seller',
        'auth' => 'google',
        'gmail_linked' => !empty($tokens['access_token']),
    ];
    $_SESSION['google'] = $user;
    $_SESSION['gmail_linked'] = $user['gmail_linked'];
    $_SESSION['email'] = $email;
    $_SESSION['user_email'] = $email;
    $_SESSION['username'] = $email;
    $_SESSION['name'] = $name;
    $_SESSION['logged_in'] = true;
    $_SESSION['auth'] = true;
    $_SESSION['seller'] = true;
    $_SESSION['user'] = $user;

    $keys = bam_google_detect_session_keys(bam_google_read_nearby_php());
    $emailKeys = ['email', 'user_email', 'username', 'login', 'mail', 'seller_email'];
    $idKeys = ['uid', 'user_id', 'id', 'seller_id'];
    $nameKeys = ['name', 'full_name', 'display_name', 'seller_name'];
    foreach ($keys as $key) {
        $lk = strtolower($key);
        if (in_array($lk, $emailKeys, true) || str_contains($lk, 'email')) {
            $_SESSION[$key] = $email;
        } elseif (in_array($lk, $idKeys, true)) {
            $_SESSION[$key] = $user['id'];
        } elseif (in_array($lk, $nameKeys, true)) {
            $_SESSION[$key] = $name;
        } elseif (in_array($lk, ['logged_in', 'auth', 'authenticated', 'ok', 'seller'], true)) {
            $_SESSION[$key] = true;
        } elseif ($lk === 'user' && is_array($_SESSION['user'] ?? null)) {
            $_SESSION[$key] = $user;
        }
    }
}

function bam_google_token_dir(): string
{
    $dir = __DIR__ . '/google-tokens';
    if (!is_dir($dir)) {
        mkdir($dir, 0700, true);
    }
    return $dir;
}

function bam_google_token_path(string $email): string
{
    return bam_google_token_dir() . '/' . hash('sha256', strtolower(trim($email))) . '.json';
}

function bam_google_save_tokens(string $email, array $tokens): void
{
    $payload = [
        'email' => strtolower(trim($email)),
        'saved_at' => gmdate('c'),
        'access_token' => $tokens['access_token'] ?? '',
        'refresh_token' => $tokens['refresh_token'] ?? '',
        'expires_at' => time() + (int) ($tokens['expires_in'] ?? 3600) - 30,
        'scope' => $tokens['scope'] ?? '',
        'token_type' => $tokens['token_type'] ?? 'Bearer',
    ];
    $existing = bam_google_load_tokens($email);
    if ($existing && empty($payload['refresh_token']) && !empty($existing['refresh_token'])) {
        $payload['refresh_token'] = $existing['refresh_token'];
    }
    file_put_contents(bam_google_token_path($email), json_encode($payload, JSON_UNESCAPED_SLASHES), LOCK_EX);
}

function bam_google_load_tokens(string $email): ?array
{
    $path = bam_google_token_path($email);
    if (!is_file($path)) {
        return null;
    }
    $data = json_decode((string) file_get_contents($path), true);
    return is_array($data) ? $data : null;
}

function bam_google_http(string $url, array $opts = []): array
{
    $ch = curl_init($url);
    $headers = $opts['headers'] ?? [];
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 20,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_CUSTOMREQUEST => $opts['method'] ?? 'GET',
    ]);
    if (isset($opts['body'])) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $opts['body']);
    }
    $raw = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    $json = is_string($raw) ? json_decode($raw, true) : null;
    return ['code' => $code, 'json' => is_array($json) ? $json : [], 'raw' => (string) $raw, 'error' => $err];
}

function bam_google_exchange_code(string $code): array
{
    $cfg = bam_google_config();
    $res = bam_google_http('https://oauth2.googleapis.com/token', [
        'method' => 'POST',
        'headers' => ['Content-Type: application/x-www-form-urlencoded'],
        'body' => http_build_query([
            'code' => $code,
            'client_id' => $cfg['client_id'],
            'client_secret' => $cfg['client_secret'],
            'redirect_uri' => $cfg['redirect_uri'],
            'grant_type' => 'authorization_code',
        ]),
    ]);
    return $res['json'];
}

function bam_google_userinfo(string $accessToken): array
{
    $res = bam_google_http('https://www.googleapis.com/oauth2/v2/userinfo', [
        'headers' => ['Authorization: Bearer ' . $accessToken],
    ]);
    return $res['json'];
}

function bam_google_refresh(array $tokens): array
{
    if (empty($tokens['refresh_token'])) {
        return $tokens;
    }
    $cfg = bam_google_config();
    $res = bam_google_http('https://oauth2.googleapis.com/token', [
        'method' => 'POST',
        'headers' => ['Content-Type: application/x-www-form-urlencoded'],
        'body' => http_build_query([
            'client_id' => $cfg['client_id'],
            'client_secret' => $cfg['client_secret'],
            'refresh_token' => $tokens['refresh_token'],
            'grant_type' => 'refresh_token',
        ]),
    ]);
    $json = $res['json'];
    if (empty($json['access_token'])) {
        return $tokens;
    }
    $merged = array_merge($tokens, $json);
    bam_google_save_tokens($tokens['email'] ?? '', $merged);
    return bam_google_load_tokens($tokens['email'] ?? '') ?? $merged;
}

function bam_google_valid_access_token(string $email): ?string
{
    $tokens = bam_google_load_tokens($email);
    if (!$tokens) {
        return null;
    }
    if ((int) ($tokens['expires_at'] ?? 0) > time() && !empty($tokens['access_token'])) {
        return $tokens['access_token'];
    }
    $tokens = bam_google_refresh($tokens);
    return $tokens['access_token'] ?? null;
}

function bam_google_page(string $title, string $body): string
{
    $title = htmlspecialchars($title, ENT_QUOTES, 'UTF-8');
    return <<<HTML
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{$title} · Exclusive Sellers</title>
<style>
body{margin:0;background:#0a0a0a;color:#f5f5f5;font-family:"Source Sans 3","Segoe UI",sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.card{max-width:420px;width:100%;background:#111;border:1px solid #2e2e2e;border-radius:14px;padding:28px}
h1{font-size:18px;margin:0 0 12px}
p{color:#a3a3a3;font-size:14px;line-height:1.45}
a{color:#ffc107}
.motto{background:#ffc107;color:#111;font-weight:900;font-size:11px;text-align:center;padding:9px 8px;border-radius:6px;margin:0 0 18px;letter-spacing:.02em}
.err{color:#fca5a5}
</style></head><body><div class="card">
<div class="motto">EXCLUSIVE SELLERS</div>
{$body}
</div></body></html>
HTML;
}
