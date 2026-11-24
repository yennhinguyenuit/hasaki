<?php
/** Run only this test order's real WooCommerce webhook actions. */
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$root = $argv[1] ?? '';
$mode = $argv[2] ?? '';
$order_id = (int) ( $argv[3] ?? 0 );
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/shopdongho/';
$_SERVER['REQUEST_METHOD'] = 'GET';
require $root . '/wp-load.php';
$admins = get_users( array( 'role' => 'administrator', 'number' => 1 ) );
if ( ! $admins || ! function_exists( 'hasaki_crm_sync_webhooks' ) ) { throw new RuntimeException( 'Existing admin, WooCommerce and configured bridge required.' ); }
wp_set_current_user( $admins[0]->ID );

// Test-only guards in this CLI request. Never persistently alter store hooks,
// stock, sales counters, customer records, or send test notification emails.
foreach ( WC()->mailer()->get_emails() as $email ) {
	add_filter( 'woocommerce_email_enabled_' . $email->id, '__return_false' );
}
foreach ( array( 'processing', 'completed', 'on-hold' ) as $status ) {
	remove_action( 'woocommerce_order_status_' . $status, 'wc_maybe_reduce_stock_levels' );
	remove_action( 'woocommerce_order_status_' . $status, 'wc_update_total_sales_counts' );
}
remove_action( 'woocommerce_payment_complete', 'wc_maybe_reduce_stock_levels' );

$receipts = array();
add_action( 'woocommerce_webhook_delivery', function ( $args, $response, $duration, $arg, $webhook_id ) use ( &$receipts ) {
	$body = json_decode( wp_remote_retrieve_body( $response ), true );
	$receipts[] = array(
		'webhook_id' => $webhook_id, 'order_id' => $arg,
		'topic' => $args['headers']['X-WC-Webhook-Topic'],
		'delivery_id' => $args['headers']['X-WC-Webhook-Delivery-ID'],
		'http_status' => is_wp_error( $response ) ? 0 : wp_remote_retrieve_response_code( $response ),
		'result' => $body['message'] ?? null,
	);
}, 10, 5 );

function hsk_process_test_order_queue( $order_id ) {
	global $wc_queued_webhooks;
	wc_webhook_execute_queue();
	$wc_queued_webhooks = array();
	remove_action( 'shutdown', 'wc_webhook_execute_queue' );
	$ids = WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) );
	// Run this test's creation action before its update action, as required by
	// the receiver contract. The scheduler's newest-first listing is not a
	// delivery ordering guarantee.
	usort( $ids, function ( $left, $right ) {
		$a = new WC_Webhook( $left ); $b = new WC_Webhook( $right );
		return ( 'order.created' === $a->get_topic() ? 0 : 1 ) <=> ( 'order.created' === $b->get_topic() ? 0 : 1 );
	} );
	$processed = array();
	foreach ( $ids as $id ) {
		$webhook = new WC_Webhook( $id );
		if ( ! hasaki_crm_is_configured_target( $webhook->get_delivery_url() ) ) { continue; }
		$actions = as_get_scheduled_actions( array(
			'hook' => 'woocommerce_deliver_webhook_async', 'group' => 'woocommerce-webhooks',
			'args' => array( 'webhook_id' => (int) $id, 'arg' => (int) $order_id ),
			'status' => ActionScheduler_Store::STATUS_PENDING, 'per_page' => 20,
		), 'ids' );
		foreach ( $actions as $action_id ) {
			ActionScheduler_QueueRunner::instance()->process_action( $action_id, 'A4.8 local verification' );
			$processed[] = array( 'action_id' => $action_id, 'status' => ActionScheduler::store()->get_status( $action_id ) );
		}
	}
	return $processed;
}

if ( in_array( $mode, array( 'create', 'cron-create' ), true ) ) {
	$products = wc_get_products( array( 'status' => 'publish', 'type' => 'simple', 'limit' => 200, 'orderby' => 'ID', 'order' => 'ASC' ) );
	$product = null;
	foreach ( $products as $candidate ) {
		if ( $candidate->get_sku() && (float) $candidate->get_price() > 0 ) {
			$product = $candidate; break;
		}
	}
	if ( ! $product ) { throw new RuntimeException( 'An existing priced SKU product is required.' ); }
	$order = wc_create_order( array( 'status' => 'pending', 'customer_id' => 0, 'created_via' => 'a48-integration-test' ) );
	$order->set_address( array( 'first_name' => 'A4.8 WP TEST', 'last_name' => 'Guest',
		'phone' => '0900000000', 'email' => 'a48-wp-test@example.invalid', 'country' => 'VN' ), 'billing' );
	$order->set_currency( 'VND' );
	$order->set_payment_method( 'cod' );
	$order->set_customer_note( 'A4.8 local integration test; no real fulfillment or payment.' );
	$order->update_meta_data( '_a48_integration_test', 'yes' );
	$order->add_product( $product, 1 );
	$order->calculate_totals( false );
	$order->save();
	$order_id = $order->get_id();
	$actions = 'cron-create' === $mode ? array() : hsk_process_test_order_queue( $order_id );
} else {
	$order = wc_get_order( $order_id );
	if ( ! $order || 'a48-integration-test' !== $order->get_created_via() || 'yes' !== $order->get_meta( '_a48_integration_test' ) ) {
		throw new RuntimeException( 'Only an order created by this integration test can be changed.' );
	}
	if ( 'resume-created' === $mode ) {
		foreach ( WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) ) as $id ) {
			$webhook = new WC_Webhook( $id );
			if ( hasaki_crm_is_configured_target( $webhook->get_delivery_url() ) ) { $webhook->process( $order_id ); }
		}
		$actions = hsk_process_test_order_queue( $order_id );
	} elseif ( in_array( $mode, array( 'update', 'cron-update' ), true ) ) {
		$stamp = max( time(), $order->get_date_modified()->getTimestamp() + 2 );
		$order->set_status( 'processing' );
		$order->set_date_paid( $stamp );
		$order->set_date_modified( $stamp );
		$order->set_transaction_id( 'A48-TEST-' . $order_id );
		$order->save();
		$actions = 'cron-update' === $mode ? array() : hsk_process_test_order_queue( $order_id );
	} elseif ( 'replay' === $mode ) {
		$actions = array();
		foreach ( WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) ) as $id ) {
			$webhook = new WC_Webhook( $id );
			if ( 'order.updated' === $webhook->get_topic() && hasaki_crm_is_configured_target( $webhook->get_delivery_url() ) ) {
				$webhook->deliver( $order_id );
			}
		}
	} else { throw new RuntimeException( 'Unknown test phase.' ); }
}
$report = array( 'mode' => $mode, 'order_id' => $order_id, 'order_status' => $order->get_status(),
	'amount' => $order->get_total(), 'scheduled_actions' => $actions, 'deliveries' => $receipts );
$report['manual_action_execution'] = ! str_starts_with( $mode, 'cron-' );
echo json_encode( $report, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT ), PHP_EOL;
if ( ! $receipts && ! str_starts_with( $mode, 'cron-' ) ) { throw new RuntimeException( 'No native webhook delivery was executed.' ); }
foreach ( $receipts as $receipt ) {
	if ( 200 !== $receipt['http_status'] || empty( $receipt['result']['ok'] ) ) {
		throw new RuntimeException( 'Native WooCommerce delivery failed; inspect the sanitized test report.' );
	}
}
