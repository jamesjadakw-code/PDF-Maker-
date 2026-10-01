<?php
require_once __DIR__ . '/google-oauth.php';
bam_google_start_session();

function bam_google_fail(string $msg): void
{
    http_response_code(403);
    echo bam_google_page('Google login failed', '<h1>Could not sign in</h1><p class="err">' . htmlspecialchars($msg, ENT_QUOTES, 'UTF-8') . '</p><p><a href="login.php">Try again</a></p>');
    exit;
}

$cfg = bam_google_config();
$profile = null;
$tokens = [];

if (!empty($cfg['mock_google']) && isset($_GET['mock'])) {
    $profile = [
        'email' => 'sales@bigassmotors.com',
        'name' => 'Big Ass Motors Sales',
        'id' => 'mock-sales',
    ];
    $tokens = [
        'access_token' => 'mock-access',
        'refresh_token' => 'mock-refresh',
        'expires_in' => 3600,
        'scope' => implode(' ', $cfg['scopes']),
    ];
} else {
    $state = (string) ($_GET['state'] ?? '');
    $expected = (string) ($_SESSION['google_oauth_state'] ?? '');
    unset($_SESSION['google_oauth_state']);
    if ($state === '' || $expected === '' || !hash_equals($expected, $state)) {
        bam_google_fail('Google sign-in expired. Reload login and try Continue with Google again.');
    }
    if (!empty($_GET['error'])) {
        bam_google_fail('Google returned: ' . (string) $_GET['error']);
    }
    $code = (string) ($_GET['code'] ?? '');
    if ($code === '') {
        bam_google_fail('Google did not send an authorization code.');
    }
    $tokens = bam_google_exchange_code($code);
    if (empty($tokens['access_token'])) {
        bam_google_fail('Google token exchange failed. Check client id, secret, and redirect URI.');
    }
    $profile = bam_google_userinfo($tokens['access_token']);
}

$email = strtolower(trim((string) ($profile['email'] ?? '')));
if ($email === '') {
    bam_google_fail('Google did not return an email address.');
}
if (!bam_google_allowed($email)) {
    bam_google_fail('That Google account is not on the BAM CRM allow-list: ' . $email);
}

bam_google_save_tokens($email, $tokens);
bam_google_bridge_session($profile, $tokens);
$_SESSION['gmail_tokens_email'] = $email;

$next = (string) ($_SESSION['google_next'] ?? 'index.php');
unset($_SESSION['google_next']);
if ($next === '' || str_contains($next, '://') || str_starts_with($next, '//')) {
    $next = 'index.php';
}

header('Location: google-gmail.php?welcome=1&next=' . rawurlencode($next));
exit;
