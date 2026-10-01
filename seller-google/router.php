<?php
/**
 * PHP built-in server router so /login.php hits the Google wrap
 * (Hostinger uses .htaccess instead).
 */
$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
$file = __DIR__ . $uri;
if ($uri === '/' || $uri === '') {
    require __DIR__ . '/google-login-wrap.php';
    return true;
}
if (basename($uri) === 'login.php') {
    require __DIR__ . '/google-login-wrap.php';
    return true;
}
if (is_file($file)) {
    return false;
}
http_response_code(404);
echo 'Not found';
return true;
