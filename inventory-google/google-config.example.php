<?php
/**
 * Copy this file to google-config.php on the CRM server
 * (public_html/inventory/google-config.php) and fill in the Google Cloud
 * OAuth client. Do not commit google-config.php.
 *
 * Google Cloud Console → APIs & Services → Credentials → Create OAuth client
 * Application type: Web application
 * Authorized redirect URI:
 *   https://bigassmotorscrm.bigassmotors.com/inventory/google-callback.php
 * Enable Gmail API on the same project.
 */
return [
    'client_id' => 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com',
    'client_secret' => 'YOUR_GOOGLE_CLIENT_SECRET',
    'redirect_uri' => 'https://bigassmotorscrm.bigassmotors.com/inventory/google-callback.php',
    'allowed_domains' => ['bigassmotors.com'],
    'allowed_emails' => [
        'jamesjadakw@gmail.com',
        'sales@bigassmotors.com',
        'mattc@bigassmotors.com',
        'chris@bigassmotors.com',
        'nsales@bigassmotors.com',
    ],
    'session_name' => 'BAMCRM',
    'mock_google' => false,
];
