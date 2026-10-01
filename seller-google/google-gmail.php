<?php
require_once __DIR__ . '/google-oauth.php';
bam_google_start_session();

$email = strtolower((string) ($_SESSION['gmail_tokens_email'] ?? $_SESSION['email'] ?? ''));
if ($email === '' || empty($_SESSION['logged_in'])) {
    header('Location: login.php');
    exit;
}

$home = (string) (bam_google_config()['home_after_login'] ?? 'index.php');
$next = (string) ($_GET['next'] ?? $home);
if ($next === '' || str_contains($next, '://') || str_starts_with($next, '//')) {
    $next = $home;
}

$cfg = bam_google_config();
$subjects = [];
$error = '';
$linked = false;

if (!empty($cfg['mock_google'])) {
    $linked = true;
    $subjects = [
        ['from' => 'Big Ass Motors', 'subject' => 'Your machine is live with Exclusive Sellers'],
        ['from' => 'Buyer desk', 'subject' => 'New brochure open on your listing'],
    ];
} else {
    $access = bam_google_valid_access_token($email);
    if ($access) {
        $linked = true;
        $list = bam_google_http('https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5&q=in:inbox', [
            'headers' => ['Authorization: Bearer ' . $access],
        ]);
        foreach (($list['json']['messages'] ?? []) as $msg) {
            $id = $msg['id'] ?? '';
            if ($id === '') {
                continue;
            }
            $full = bam_google_http('https://gmail.googleapis.com/gmail/v1/users/me/messages/' . rawurlencode($id) . '?format=metadata&metadataHeaders=Subject&metadataHeaders=From', [
                'headers' => ['Authorization: Bearer ' . $access],
            ]);
            $from = '';
            $subject = '(no subject)';
            foreach (($full['json']['payload']['headers'] ?? []) as $header) {
                if (strcasecmp($header['name'] ?? '', 'From') === 0) {
                    $from = $header['value'] ?? '';
                }
                if (strcasecmp($header['name'] ?? '', 'Subject') === 0) {
                    $subject = $header['value'] ?? $subject;
                }
            }
            $subjects[] = ['from' => $from, 'subject' => $subject];
        }
        if (($list['code'] ?? 0) >= 400) {
            $error = 'Gmail API ' . $list['code'] . ': inbox read was denied. The Google account is signed in; enable Gmail API and keep the gmail.readonly scope.';
        }
    } else {
        $error = 'Signed in, but Gmail is not linked yet. Use Continue with Google again and accept Gmail access.';
    }
}

$safeEmail = htmlspecialchars($email, ENT_QUOTES, 'UTF-8');
$safeNext = htmlspecialchars($next, ENT_QUOTES, 'UTF-8');
$rows = '';
foreach ($subjects as $row) {
    $rows .= '<li><strong>' . htmlspecialchars($row['subject'], ENT_QUOTES, 'UTF-8') . '</strong><br><span>' . htmlspecialchars($row['from'], ENT_QUOTES, 'UTF-8') . '</span></li>';
}
if ($rows === '' && $linked && $error === '') {
    $rows = '<li>Inbox linked. No recent messages to preview.</li>';
}
$errHtml = $error !== '' ? '<p class="err">' . htmlspecialchars($error, ENT_QUOTES, 'UTF-8') . '</p>' : '';
$status = $linked ? 'Gmail linked' : 'Gmail not linked';

echo bam_google_page(
    'Gmail linked',
    '<h1>' . $status . '</h1>
     <p>Signed in as <strong style="color:#fff">' . $safeEmail . '</strong>. This Google account is now the mailbox Exclusive Sellers will use for your session.</p>
     ' . $errHtml . '
     <ul style="padding-left:18px;color:#ddd;font-size:13px;line-height:1.5">' . $rows . '</ul>
     <p><a href="' . $safeNext . '">Open Exclusive Sellers →</a></p>'
);
