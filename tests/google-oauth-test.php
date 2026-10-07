<?php
declare(strict_types=1);

require_once __DIR__ . '/../inventory-google/google-oauth.php';

function assert_true(bool $cond, string $msg): void
{
    if (!$cond) {
        fwrite(STDERR, "FAIL: $msg\n");
        exit(1);
    }
    echo "ok  $msg\n";
}

assert_true(bam_google_allowed('sales@bigassmotors.com'), 'domain allow-list accepts @bigassmotors.com');
assert_true(bam_google_allowed('jamesjadakw@gmail.com'), 'explicit email allow-list accepts James');
assert_true(!bam_google_allowed('random@gmail.com'), 'unknown gmail is rejected');
assert_true(!bam_google_allowed('not-an-email'), 'garbage email is rejected');

$fixture = file_get_contents(__DIR__ . '/fixtures/login.php');
$injected = bam_google_inject_button($fixture);
assert_true(str_contains($injected, 'Continue with Google'), 'login HTML gets Google button');
assert_true(str_contains($injected, 'links this Gmail inbox'), 'button copy mentions Gmail link');
assert_true(str_contains($injected, 'class="btn btn-y"'), 'password Log in button is still present');
$twice = bam_google_inject_button($injected);
assert_true(substr_count($twice, 'bam-google-login') === substr_count($injected, 'bam-google-login'), 'inject is idempotent');

$src = '$_SESSION[\'uid\'] = 1; $_SESSION["email"] = $row["email"]; $_SESSION[\'logged_in\'] = true;';
$keys = bam_google_detect_session_keys($src);
assert_true($keys === ['uid', 'email', 'logged_in'], 'session key detection reads assignments');

$state = 'abc123';
$url = bam_google_oauth_url($state, 'https://bigassmotorscrm.bigassmotors.com/inventory/google-callback.php');
assert_true(str_contains($url, 'accounts.google.com/o/oauth2/v2/auth'), 'OAuth URL is Google');
assert_true(str_contains($url, 'state=abc123'), 'OAuth URL carries CSRF state');
assert_true(str_contains($url, rawurlencode('https://www.googleapis.com/auth/gmail.readonly')), 'OAuth URL asks for Gmail read');
assert_true(str_contains($url, rawurlencode('https://www.googleapis.com/auth/gmail.send')), 'OAuth URL asks for Gmail send');
assert_true(str_contains($url, 'access_type=offline'), 'OAuth URL requests refresh token');

$wrap = file_get_contents(__DIR__ . '/../inventory-google/google-login-wrap.php');
assert_true(str_contains($wrap, 'bam_google_inject_button'), 'wrap injects on GET');
assert_true(str_contains($wrap, "require \$login"), 'wrap still runs original password POST');

$ht = file_get_contents(__DIR__ . '/../inventory-google/.htaccess');
assert_true(str_contains($ht, 'google-login-wrap.php'), '.htaccess rewrites login.php to wrap');

echo "ALL TESTS PASSED\n";
