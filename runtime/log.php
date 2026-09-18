<?php
/*
 * TilTale study logger (PHP 7.4+). Receives one JSON event, or a JSON array of events of the
 * same visit, per POST from tiltale.js and appends them to logs/<participant_id>--<visit_id>.jsonl
 * next to this file. Each page load is a new visit, so opening the story twice never overwrites a log.
 * logs/.htaccess blocks browsing the logs on Apache; see the README for other servers.
 *
 * When the studio put log-key.pem (the project's public key) next to this file, every line is
 * encrypted before it is written: a fresh AES-256-GCM key per event, wrapped with RSA-OAEP.
 * Only the private key file, which the studio handed out once, can read them (see ETHICS.md).
 * The scheme is mirrored by studio/services/log_keys.py.
 */
declare(strict_types=1);

header('Cache-Control: no-store');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    exit;
}

$body = file_get_contents('php://input', false, null, 0, 65536);
$decoded = json_decode($body === false ? '' : $body, true);
$events = is_array($decoded) && isset($decoded[0]) ? $decoded : [$decoded];  /* a list of events, or one */
$first = $events[0] ?? null;
foreach ($events as $event) {
    if (!is_array($event) || !is_string($event['participant_id'] ?? null)
        || !is_string($event['visit_id'] ?? null) || !is_string($event['event'] ?? null)
        || $event['participant_id'] !== $first['participant_id'] || $event['visit_id'] !== $first['visit_id']) {
        http_response_code(400);  /* not an event, or events of two visits in one request */
        exit;
    }
}

/* Same rule as tiltale.js and the TilTale studio: unsafe characters become "-". */
function tiltale_safe_name(string $value): string
{
    return substr(trim((string) preg_replace('/[^A-Za-z0-9_-]+/', '-', $value), '-'), 0, 80);
}

$participant = tiltale_safe_name($first['participant_id']);
$visit = tiltale_safe_name($first['visit_id']);
if ($participant === '' || $visit === '') {
    http_response_code(400);
    exit;
}

$directory = __DIR__ . '/logs';
if (!is_dir($directory) && mkdir($directory, 0750, true)) {
    file_put_contents($directory . '/.htaccess', "Require all denied\n");
}

/* One encrypted line: {"enc": wrapped key, "iv", "tag", "data"}, all base64. */
function tiltale_encrypt(string $plain, string $publicKey): ?string
{
    $key = random_bytes(32);
    $iv = random_bytes(12);
    $tag = '';
    $data = openssl_encrypt($plain, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag, '', 16);
    $wrapped = '';
    if ($data === false || !openssl_public_encrypt($key, $wrapped, $publicKey, OPENSSL_PKCS1_OAEP_PADDING)) {
        return null;
    }
    return json_encode([
        'enc' => base64_encode($wrapped), 'iv' => base64_encode($iv),
        'tag' => base64_encode($tag), 'data' => base64_encode($data),
    ]);
}

$publicKeyFile = __DIR__ . '/log-key.pem';
$publicKey = is_file($publicKeyFile) ? (string) file_get_contents($publicKeyFile) : null;
$lines = '';
foreach ($events as $event) {
    $event['received_at'] = gmdate('Y-m-d\TH:i:s\Z');
    $line = json_encode($event, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($publicKey !== null) {
        $line = tiltale_encrypt($line, $publicKey);
        if ($line === null) {
            http_response_code(500);  /* the openssl extension is missing or the key file is damaged: nothing is written */
            exit;
        }
    }
    $lines .= $line . "\n";
}
$file = $directory . '/' . $participant . '--' . $visit . '.jsonl';
http_response_code(file_put_contents($file, $lines, FILE_APPEND | LOCK_EX) === false ? 500 : 204);
