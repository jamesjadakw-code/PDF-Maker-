<?php
/**
 * Copy this file to google-config.php on the public site
 * (public_html/seller/google-config.php) and fill in the Google Cloud
 * OAuth client. Do not commit google-config.php.
 *
 * Use the SAME Web client as BAM CRM. Add this extra Authorized redirect URI:
 *   https://www.bigassmotors.com/seller/google-callback.php
 * Enable Gmail API on the same project.
 *
 * Exclusive Sellers is a public portal: any Google account with a real email
 * can sign in. Staff CRM login stays on the allow-list in /inventory/.
 */
return [
    'client_id' => 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com',
    'client_secret' => 'YOUR_GOOGLE_CLIENT_SECRET',
    'redirect_uri' => 'https://www.bigassmotors.com/seller/google-callback.php',
    'allowed_domains' => [],
    'allowed_emails' => [],
    'allow_any_google' => true,
    'session_name' => 'BAMSESS',
    'portal' => 'seller',
    'home_after_login' => 'index.php',
    'mock_google' => false,
];
