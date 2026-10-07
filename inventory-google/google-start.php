<?php
require_once __DIR__ . '/google-oauth.php';
bam_google_start_session();

if (!empty($_GET['next'])) {
    $_SESSION['google_next'] = (string) $_GET['next'];
} elseif (!empty($_POST['next'])) {
    $_SESSION['google_next'] = (string) $_POST['next'];
}

if (!bam_google_configured()) {
    http_response_code(503);
    echo bam_google_page(
        'Google login not configured',
        '<h1>Google login is not wired yet</h1>
         <p>Copy <code>google-config.example.php</code> to <code>google-config.php</code> and paste a Google Cloud OAuth Web client id and secret. Redirect URI must be:</p>
         <p><code>' . htmlspecialchars(bam_google_config()['redirect_uri'], ENT_QUOTES, 'UTF-8') . '</code></p>
         <p><a href="login.php">← Back to login</a></p>'
    );
    exit;
}

if (!empty(bam_google_config()['mock_google'])) {
    header('Location: google-callback.php?mock=1');
    exit;
}

$state = bin2hex(random_bytes(16));
$_SESSION['google_oauth_state'] = $state;
header('Location: ' . bam_google_oauth_url($state));
exit;
