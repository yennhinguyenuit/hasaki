<?php
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$root = $argv[1] ?? '';
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/shopdongho/';
$_SERVER['REQUEST_METHOD'] = 'GET';
require $root . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
$admins = get_users( array( 'role' => 'administrator', 'number' => 1 ) );
if ( ! $admins ) { throw new RuntimeException( 'Existing WordPress administrator required.' ); }
wp_set_current_user( $admins[0]->ID );
$plugin = 'hasaki-crm-bridge/hasaki-crm-bridge.php';
if ( ! is_plugin_active( $plugin ) ) {
	$result = activate_plugin( $plugin );
	if ( is_wp_error( $result ) ) { throw new RuntimeException( 'Bridge plugin activation failed.' ); }
}
$ids = hasaki_crm_sync_webhooks();
if ( is_wp_error( $ids ) ) { throw new RuntimeException( $ids->get_error_message() ); }
$report = array( 'plugin_active' => is_plugin_active( $plugin ), 'webhooks' => array() );
foreach ( $ids as $topic => $id ) {
	$webhook = new WC_Webhook( $id );
	$ping = $webhook->deliver_ping();
	if ( is_wp_error( $ping ) ) { throw new RuntimeException( $ping->get_error_message() ); }
	$report['webhooks'][] = array( 'id' => $id, 'topic' => $topic, 'status' => $webhook->get_status(),
		'delivery_url' => $webhook->get_delivery_url(), 'activation_ping' => 'Passed' );
}
echo json_encode( $report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ), PHP_EOL;
