<?php
/** Read cron/queue evidence. Never execute a queued action or call wp-cron. */
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$root = $argv[1] ?? '';
$order_id = (int) ( $argv[2] ?? 0 );
$config_source = file_get_contents( $root . '/wp-config.php' );
$configured_disable = null;
if ( preg_match( '/define\s*\(\s*[\'\"]DISABLE_WP_CRON[\'\"]\s*,\s*(true|false|1|0)\s*\)/i', $config_source, $matches ) ) {
	$configured_disable = in_array( strtolower( $matches[1] ), array( 'true', '1' ), true );
}
// This read-only CLI inspector does not itself launch cron or async runners.
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080'; $_SERVER['REQUEST_URI'] = '/shopdongho/'; $_SERVER['REQUEST_METHOD'] = 'GET';
require $root . '/wp-load.php';
global $wpdb;
$events = array();
foreach ( _get_cron_array() as $timestamp => $hooks ) {
	foreach ( $hooks as $hook => $entries ) {
		if ( 'action_scheduler_run_queue' !== $hook ) { continue; }
		foreach ( $entries as $event ) {
			$events[] = array( 'hook' => $hook, 'timestamp_utc' => (int) $timestamp,
				'schedule' => $event['schedule'], 'interval' => $event['interval'] ?? null );
		}
	}
}
$report = array(
	'observed_at_utc' => gmdate( DATE_ATOM ), 'home_url' => home_url( '/' ),
	'disable_wp_cron_defined_in_site_config' => null !== $configured_disable,
	'disable_wp_cron_configured' => $configured_disable ?? false,
	'inspector_only_disable_wp_cron' => true,
	'action_scheduler_wp_cron_events' => $events,
	'doing_cron_lock' => get_transient( 'doing_cron' ),
	'queue_counts' => $wpdb->get_results( "SELECT hook,status,COUNT(*) AS count FROM {$wpdb->prefix}actionscheduler_actions GROUP BY hook,status ORDER BY hook,status", ARRAY_A ),
);
if ( $order_id ) {
	$report['order_id'] = $order_id;
	$report['actions'] = array();
	foreach ( WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) ) as $webhook_id ) {
		$webhook = new WC_Webhook( $webhook_id );
		if ( ! hasaki_crm_is_configured_target( $webhook->get_delivery_url() ) ) { continue; }
		$ids = as_get_scheduled_actions( array( 'hook' => 'woocommerce_deliver_webhook_async',
			'group' => 'woocommerce-webhooks', 'args' => array( 'webhook_id' => (int) $webhook_id, 'arg' => $order_id ),
			'per_page' => 50, 'orderby' => 'action_id', 'order' => 'ASC' ), 'ids' );
		foreach ( $ids as $id ) {
			$report['actions'][] = array( 'action_id' => $id, 'topic' => $webhook->get_topic(),
				'status' => ActionScheduler::store()->get_status( $id ),
				'logs' => $wpdb->get_results( $wpdb->prepare(
					"SELECT message,log_date_gmt FROM {$wpdb->prefix}actionscheduler_logs WHERE action_id=%d ORDER BY log_id", $id ), ARRAY_A ) );
		}
	}
}
echo json_encode( $report, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT ), PHP_EOL;
