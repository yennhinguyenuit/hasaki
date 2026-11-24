<?php
/** Focused adapter tests using WordPress API doubles. This is NOT a WordPress installation test. */
define( 'ABSPATH', __DIR__ );
define( 'HASAKI_CRM_BASE_URL', 'http://crm.test:8000' );
define( 'HASAKI_CRM_API_KEY', 'test-key' );
define( 'HASAKI_CRM_API_SECRET', 'test-secret' );

class WP_Error {
	public $code;
	public function __construct( $code, $message ) { $this->code = $code; }
}
function add_filter( ...$args ) {}
function add_action( ...$args ) {}
function add_shortcode( ...$args ) {}
function is_wp_error( $result ) { return $result instanceof WP_Error; }
function wp_json_encode( $value ) { return json_encode( $value ); }
function wp_remote_retrieve_response_code( $response ) { return $response['status']; }
function wp_remote_retrieve_body( $response ) { return $response['body']; }
function wp_remote_post( $url, $args ) {
	$GLOBALS['requests'][] = array( 'url' => $url, 'args' => $args );
	return array_shift( $GLOBALS['responses'] );
}
require __DIR__ . '/../wordpress-plugin/hasaki-crm-bridge/hasaki-crm-bridge.php';

function verify( $condition, $message ) {
	if ( ! $condition ) { throw new RuntimeException( $message ); }
}
$payload = array( 'submission_id' => 'adapter-test', 'consent' => true );
$success = array( 'status' => 200, 'body' => json_encode( array( 'message' => array(
	'ok' => true, 'code' => 'PROCESSED', 'data' => array( 'lead' => 'test-lead' ), 'idempotent' => false,
) ) ) );
$GLOBALS['requests'] = array();
$GLOBALS['responses'] = array( $success );
$result = hasaki_crm_send_lead( $payload );
verify( 'test-lead' === $result['data']['lead'], 'Must unwrap Frappe message.' );
$request = $GLOBALS['requests'][0];
verify( 'token test-key:test-secret' === $request['args']['headers']['Authorization'], 'API Token must be server-side.' );
verify( 0 === $request['args']['redirection'], 'Credentials must never follow redirects.' );
verify( $payload === json_decode( $request['args']['body'], true ), 'Payload must be JSON.' );

$GLOBALS['requests'] = array();
$GLOBALS['responses'] = array( new WP_Error( 'timeout', 'Timeout' ), $success );
$result = hasaki_crm_send_lead( $payload );
verify( ! is_wp_error( $result ) && 2 === count( $GLOBALS['requests'] ), 'A transient timeout must retry once.' );
verify( $GLOBALS['requests'][0]['args']['body'] === $GLOBALS['requests'][1]['args']['body'], 'Retry must preserve the submission ID and body.' );

$GLOBALS['requests'] = array();
$GLOBALS['responses'] = array( array( 'status' => 409, 'body' => json_encode( array( 'message' => array(
	'ok' => false, 'code' => 'CONFLICT',
) ) ) ) );
verify( is_wp_error( hasaki_crm_send_lead( $payload ) ), 'Business errors must be returned to caller.' );
verify( 1 === count( $GLOBALS['requests'] ), 'Do not retry business conflicts.' );

$GLOBALS['requests'] = array();
$payload['consent'] = false;
verify( is_wp_error( hasaki_crm_send_lead( $payload ) ), 'Consent is required.' );
verify( 0 === count( $GLOBALS['requests'] ), 'Do not deliver when consent is false.' );
echo "Passed: response parsing, server token, no redirects, JSON, stable retry, conflict, consent.\n";
