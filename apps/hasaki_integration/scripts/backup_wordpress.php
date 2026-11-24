<?php
/** Back up the existing site before configuration; never restore or import. */
if ( PHP_SAPI !== 'cli' ) { exit( 1 ); }
$root = $argv[1] ?? '';
$backup = $argv[2] ?? '';
$dump = $argv[3] ?? '';
if ( ! is_file( $root . '/wp-load.php' ) || ! is_file( $dump ) || ! is_dir( $backup ) ) {
	throw new RuntimeException( 'Existing WordPress, mysqldump and backup directory required.' );
}
define( 'DISABLE_WP_CRON', true );
$_SERVER['HTTP_HOST'] = 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/shopdongho/';
$_SERVER['REQUEST_METHOD'] = 'GET';
require $root . '/wp-load.php';
global $wpdb;
$target = $backup . '/wordpress-database.sql';
if ( file_exists( $target ) ) { throw new RuntimeException( 'Will not overwrite an existing backup.' ); }
$environment = getenv();
$environment['MYSQL_PWD'] = DB_PASSWORD;
$process = proc_open( array( $dump, '--host=' . DB_HOST, '--user=' . DB_USER,
	'--single-transaction', '--skip-lock-tables', '--default-character-set=utf8mb4',
	'--result-file=' . $target, DB_NAME ),
	array( 0 => array( 'pipe', 'r' ), 1 => array( 'pipe', 'w' ), 2 => array( 'pipe', 'w' ) ),
	$pipes, null, $environment, array( 'bypass_shell' => true ) );
if ( ! is_resource( $process ) ) { throw new RuntimeException( 'Cannot start database backup.' ); }
fclose( $pipes[0] );
$out = stream_get_contents( $pipes[1] );
$error = stream_get_contents( $pipes[2] );
fclose( $pipes[1] ); fclose( $pipes[2] );
if ( 0 !== proc_close( $process ) || ! is_file( $target ) || filesize( $target ) < 100 ) {
	throw new RuntimeException( 'Database backup failed. No site configuration was changed.' );
}
copy( $root . '/wp-config.php', $backup . '/wp-config.php' );
$theme_hashes = array();
$iterator = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( get_stylesheet_directory(), FilesystemIterator::SKIP_DOTS ) );
foreach ( $iterator as $file ) {
	if ( $file->isFile() ) { $theme_hashes[substr( $file->getPathname(), strlen( get_stylesheet_directory() ) )] = hash_file( 'sha256', $file->getPathname() ); }
}
ksort( $theme_hashes );
$baseline = array(
	'home_url' => home_url( '/' ), 'database' => DB_NAME,
	'active_plugins' => get_option( 'active_plugins' ),
	'theme_stylesheet' => get_option( 'stylesheet' ), 'theme_template' => get_option( 'template' ),
	'theme_file_hashes' => $theme_hashes,
	'product_count' => (array) wp_count_posts( 'product' ),
	'product_post_hash' => hash( 'sha256', wp_json_encode( $wpdb->get_results(
		"SELECT * FROM {$wpdb->posts} WHERE post_type IN ('product','product_variation') ORDER BY ID", ARRAY_A ) ) ),
	'product_meta_hash' => hash( 'sha256', wp_json_encode( $wpdb->get_results(
		"SELECT m.* FROM {$wpdb->postmeta} m INNER JOIN {$wpdb->posts} p ON p.ID=m.post_id WHERE p.post_type IN ('product','product_variation') ORDER BY m.meta_id", ARRAY_A ) ) ),
);
file_put_contents( $backup . '/baseline.json', wp_json_encode( $baseline, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ) . "\n" );
echo json_encode( array( 'backup' => $target, 'bytes' => filesize( $target ), 'baseline_saved' => true ) ), PHP_EOL;
