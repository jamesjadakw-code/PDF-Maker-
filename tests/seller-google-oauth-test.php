<?php
declare(strict_types=1);

$fixtureConfig = __DIR__ . '/fixtures/seller-google-config.php';
copy($fixtureConfig, __DIR__ . '/../seller-google/google-config.php');

require_once __DIR__ . '/../seller-google/google-oauth.php';

function assert_true(bool $cond, string $msg): void
{
    if (!$cond) {
        fwrite(STDERR, "FAIL: $msg\n");
        exit(1);
    }
    echo "ok  $msg\n";
}

assert_true(bam_google_config()['session_name'] === 'BAMSESS', 'seller portal uses BAMSESS cookie');
assert_true(bam_google_config()['portal'] === 'seller', 'portal is seller');
assert_true(bam_google_allowed('owner@gmail.com'), 'any Google email is allowed for sellers');
assert_true(bam_google_allowed('sales@bigassmotors.com'), 'staff email still allowed on seller login');
assert_true(!bam_google_allowed('not-an-email'), 'garbage email is rejected');

$fixture = file_get_contents(__DIR__ . '/fixtures/seller-login.php');
$injected = bam_google_inject_button($fixture);
assert_true(str_contains($injected, 'Continue with Google'), 'seller login HTML gets Google button');
assert_true(str_contains($injected, 'Exclusive Sellers'), 'button copy names Exclusive Sellers');
assert_true(str_contains($injected, 'links this Gmail inbox'), 'button copy mentions Gmail link');
assert_true(str_contains($injected, 'btn-yellow btn-lg'), 'password Log in button is still present');
$posGoogle = strpos($injected, 'bam-google-login');
$posEmail = strpos($injected, 'name="email"');
assert_true($posGoogle !== false && $posEmail !== false && $posGoogle < $posEmail, 'Google button sits above email/password');
$twice = bam_google_inject_button($injected);
assert_true(substr_count($twice, 'bam-google-login') === substr_count($injected, 'bam-google-login'), 'inject is idempotent');

$live = file_get_contents('/tmp/seller-login.html');
if (is_string($live) && str_contains($live, 'Exclusive Sellers Log-in')) {
    $liveInjected = bam_google_inject_button($live);
    assert_true(str_contains($liveInjected, 'Continue with Google'), 'live seller login HTML gets Google button');
    assert_true(str_contains($liveInjected, 'name="password"'), 'live password field remains');
}

$url = bam_google_oauth_url('seller-state', 'https://www.bigassmotors.com/seller/google-callback.php');
assert_true(str_contains($url, 'accounts.google.com/o/oauth2/v2/auth'), 'OAuth URL is Google');
assert_true(str_contains($url, 'state=seller-state'), 'OAuth URL carries CSRF state');
assert_true(str_contains($url, rawurlencode('https://www.bigassmotors.com/seller/google-callback.php')), 'OAuth URL uses seller redirect');
assert_true(str_contains($url, 'access_type=offline'), 'OAuth URL requests refresh token');

$wrap = file_get_contents(__DIR__ . '/../seller-google/google-login-wrap.php');
assert_true(str_contains($wrap, 'bam_google_inject_button'), 'wrap injects on GET');
assert_true(str_contains($wrap, "require \$login"), 'wrap still runs original password POST');

$ht = file_get_contents(__DIR__ . '/../seller-google/.htaccess');
assert_true(str_contains($ht, 'google-login-wrap.php'), '.htaccess rewrites login.php to wrap');

$example = require __DIR__ . '/../seller-google/google-config.example.php';
assert_true($example['session_name'] === 'BAMSESS', 'example config uses BAMSESS');
assert_true(!empty($example['allow_any_google']), 'example config allows any Google seller');
assert_true(str_contains((string) $example['redirect_uri'], '/seller/google-callback.php'), 'example redirect is seller callback');

echo "ALL SELLER TESTS PASSED\n";
