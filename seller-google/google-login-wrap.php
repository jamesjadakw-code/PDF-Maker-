<?php
/**
 * Front door for /seller/login.php (via .htaccess rewrite).
 * GET: original Exclusive Sellers login HTML + Continue with Google.
 * POST: original password login, unchanged.
 */
require_once __DIR__ . '/google-oauth.php';

$login = __DIR__ . '/login.php';
if (!is_file($login)) {
    http_response_code(500);
    echo bam_google_page('Login missing', '<h1>login.php not found</h1><p>Put these Google files in public_html/seller/ next to the Exclusive Sellers login.php.</p>');
    exit;
}

$postingPassword = $_SERVER['REQUEST_METHOD'] === 'POST'
    && (isset($_POST['password']) || isset($_POST['email']));

if ($postingPassword) {
    require $login;
    exit;
}

ob_start();
require $login;
$html = ob_get_clean();

foreach (headers_list() as $header) {
    if (stripos($header, 'Location:') === 0) {
        echo $html;
        exit;
    }
}

if ($html === '') {
    echo $html;
    exit;
}

echo bam_google_inject_button($html);
