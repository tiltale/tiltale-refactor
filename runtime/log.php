<?php
/*
 * TilTale study logger (PHP 7.4+). Receives one JSON event per POST from tiltale.js and
 * appends it to logs/<participant_id>--<visit_id>.jsonl next to this file.
 * Each page load is a new visit, so opening the story twice never overwrites a log.
 * logs/.htaccess blocks browsing the logs on Apache; see the README for other servers.
 */
declare(strict_types=1);

header('Cache-Control: no-store');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    exit;
}

$body = file_get_contents('php://input', false, null, 0, 65536);
$event = json_decode($body === false ? '' : $body, true);
if (!is_array($event) || !is_string($event['participant_id'] ?? null)
    || !is_string($event['visit_id'] ?? null) || !is_string($event['event'] ?? null)) {
    http_response_code(400);
    exit;
}

/* Same rule as tiltale.js and the TilTale studio: unsafe characters become "-". */
function tiltale_safe_name(string $value): string
{
    return substr(trim((string) preg_replace('/[^A-Za-z0-9_-]+/', '-', $value), '-'), 0, 80);
}

$participant = tiltale_safe_name($event['participant_id']);
$visit = tiltale_safe_name($event['visit_id']);
if ($participant === '' || $visit === '') {
    http_response_code(400);
    exit;
}

$directory = __DIR__ . '/logs';
if (!is_dir($directory) && mkdir($directory, 0750, true)) {
    file_put_contents($directory . '/.htaccess', "Require all denied\n");
}

$event['received_at'] = gmdate('Y-m-d\TH:i:s\Z');
$line = json_encode($event, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
$file = $directory . '/' . $participant . '--' . $visit . '.jsonl';
http_response_code(file_put_contents($file, $line, FILE_APPEND | LOCK_EX) === false ? 500 : 204);
