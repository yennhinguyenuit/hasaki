<?php
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$root = $argv[1] ?? '';
$backup = $argv[2] ?? '';
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080'; $_SERVER['REQUEST_URI'] = '/shopdongho/'; $_SERVER['REQUEST_METHOD'] = 'GET';
require $root . '/wp-load.php';
global $wpdb;
$baseline = json_decode( file_get_contents( $backup . '/baseline.json' ), true );
$theme_hashes = array();
$iterator = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( get_stylesheet_directory(), FilesystemIterator::SKIP_DOTS ) );
foreach ( $iterator as $file ) {
	if ( $file->isFile() ) { $theme_hashes[substr( $file->getPathname(), strlen( get_stylesheet_directory() ) )] = hash_file( 'sha256', $file->getPathname() ); }
}
ksort( $theme_hashes );
$product_hash = hash( 'sha256', wp_json_encode( $wpdb->get_results(
	"SELECT * FROM {$wpdb->posts} WHERE post_type IN ('product','product_variation') ORDER BY ID", ARRAY_A ) ) );
$meta_hash = hash( 'sha256', wp_json_encode( $wpdb->get_results(
	"SELECT m.* FROM {$wpdb->postmeta} m INNER JOIN {$wpdb->posts} p ON p.ID=m.post_id WHERE p.post_type IN ('product','product_variation') ORDER BY m.meta_id", ARRAY_A ) ) );
$webhooks = array();
foreach ( WC_Data_Store::load( 'webhook' )->search_webhooks( array( 'limit' => -1 ) ) as $id ) {
	$w = new WC_Webhook( $id );
	$webhooks[] = array( 'id' => $id, 'topic' => $w->get_topic(), 'status' => $w->get_status(), 'delivery_url' => $w->get_delivery_url() );
}
$report = array(
	'home_url' => home_url( '/' ), 'database' => DB_NAME,
	'published_products' => (int) wp_count_posts( 'product' )->publish,
	'product_records_unchanged' => $product_hash === $baseline['product_post_hash'],
	'product_metadata_unchanged' => $meta_hash === $baseline['product_meta_hash'],
	'theme_files_unchanged' => $theme_hashes === $baseline['theme_file_hashes'],
	'theme_selection_unchanged' => get_option( 'stylesheet' ) === $baseline['theme_stylesheet'] && get_option( 'template' ) === $baseline['theme_template'],
	'original_plugins_preserved' => ! array_diff( $baseline['active_plugins'], (array) get_option( 'active_plugins' ) ),
	'webhooks' => $webhooks,
);
echo json_encode( $report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ), PHP_EOL;
foreach ( array( 'product_records_unchanged', 'product_metadata_unchanged', 'theme_files_unchanged', 'theme_selection_unchanged', 'original_plugins_preserved' ) as $check ) {
	if ( ! $report[ $check ] ) { throw new RuntimeException( 'Preservation check failed: ' . $check ); }
}
