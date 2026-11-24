<?php
/** Inspect an existing WordPress installation without printing credentials. */
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$wp_root = $argv[1] ?? '';
if ( ! is_file( $wp_root . '/wp-load.php' ) ) { throw new RuntimeException( 'Existing WordPress root required.' ); }
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/shopdongho/';
$_SERVER['REQUEST_METHOD'] = 'GET';
require $wp_root . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
global $wpdb, $wp_version;
$themes = wp_get_theme();
$product_counts = wp_count_posts( 'product' );
$pages = get_posts( array( 'post_type' => 'page', 'post_status' => 'publish', 'numberposts' => 30 ) );
$report = array(
	'wordpress_root' => ABSPATH,
	'wordpress_version' => $wp_version,
	'home_url' => home_url( '/' ), 'site_url' => site_url( '/' ),
	'blogname' => get_option( 'blogname' ), 'database_name' => DB_NAME,
	'database_host' => DB_HOST, 'table_prefix' => $wpdb->prefix,
	'php_version' => PHP_VERSION,
	'theme' => array( 'stylesheet' => $themes->get_stylesheet(), 'template' => $themes->get_template(), 'name' => $themes->get( 'Name' ) ),
	'active_plugins' => get_option( 'active_plugins' ),
	'woo_version' => defined( 'WC_VERSION' ) ? WC_VERSION : null,
	'currency' => get_option( 'woocommerce_currency' ),
	'products' => (array) $product_counts,
	'product_skus' => $wpdb->get_col( "SELECT m.meta_value FROM {$wpdb->postmeta} m INNER JOIN {$wpdb->posts} p ON p.ID=m.post_id WHERE m.meta_key='_sku' AND p.post_type='product' AND p.post_status='publish' ORDER BY m.meta_value" ),
	'front_page' => (int) get_option( 'page_on_front' ),
	'pages' => array_map( function ( $p ) { return array( 'id' => $p->ID, 'title' => $p->post_title, 'slug' => $p->post_name ); }, $pages ),
	'existing_admins' => get_users( array( 'role' => 'administrator', 'fields' => array( 'ID', 'user_login' ) ) ),
);
if ( class_exists( 'WC_Data_Store' ) ) {
	$ids = WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) );
	$report['webhooks'] = array_map( function ( $id ) {
		$w = new WC_Webhook( $id );
		return array( 'id' => $id, 'name' => $w->get_name(), 'topic' => $w->get_topic(),
			'status' => $w->get_status(), 'delivery_url' => $w->get_delivery_url() );
	}, $ids );
}
$ping = wp_remote_get( 'http://127.0.0.1:8000/api/method/ping', array(
	'headers' => array( 'X-Frappe-Site-Name' => 'crm.localhost' ), 'timeout' => 10,
) );
$report['crm_ping'] = is_wp_error( $ping ) ? array( 'error' => $ping->get_error_message() ) : array(
	'status' => wp_remote_retrieve_response_code( $ping ), 'body' => wp_remote_retrieve_body( $ping ),
);
echo json_encode( $report, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT ), PHP_EOL;
