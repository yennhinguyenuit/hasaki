<?php
/**
 * Plugin Name: Hasaki CRM Bridge
 * Description: Server-side Lead Form delivery and native WooCommerce webhook setup for Hasaki CRM.
 * Version: 1.1.0
 * Requires PHP: 7.4
 * Requires at least: 5.9
 * License: MIT
 */

defined( 'ABSPATH' ) || exit;

function hasaki_crm_setting( $name, $default = '' ) {
	return defined( $name ) ? (string) constant( $name ) : ( getenv( $name ) ?: $default );
}

function hasaki_crm_base_url() {
	return rtrim( hasaki_crm_setting( 'HASAKI_CRM_BASE_URL' ), '/' );
}

/** Public PHP adapter for an existing form plugin. Never call from browser JS. */
function hasaki_crm_send_lead( array $payload ) {
	$base = hasaki_crm_base_url();
	$key = hasaki_crm_setting( 'HASAKI_CRM_API_KEY' );
	$secret = hasaki_crm_setting( 'HASAKI_CRM_API_SECRET' );
	if ( ! $base || ! $key || ! $secret ) {
		return new WP_Error( 'NOT_CONFIGURED', 'Lead delivery is not configured.' );
	}
	if ( ! isset( $payload['consent'] ) || true !== $payload['consent'] ) {
		return new WP_Error( 'VALIDATION_ERROR', 'Consent is required.' );
	}
	$args = array(
		'timeout' => 20,
		'redirection' => 0,
		'headers' => array(
			'Content-Type' => 'application/json',
			'Accept' => 'application/json',
			'Authorization' => 'token ' . $key . ':' . $secret,
			'X-Frappe-Site-Name' => hasaki_crm_setting( 'HASAKI_CRM_SITE', 'crm.localhost' ),
		),
		'body' => wp_json_encode( $payload ),
	);
	// Retry transient failures once with the exact same submission_id and body.
	for ( $attempt = 0; $attempt < 2; $attempt++ ) {
		$response = wp_remote_post( $base . '/api/method/hasaki_integration.wordpress.receive_lead', $args );
		if ( ! is_wp_error( $response ) && wp_remote_retrieve_response_code( $response ) < 500 ) {
			break;
		}
	}
	if ( is_wp_error( $response ) ) {
		return new WP_Error( 'DELIVERY_FAILED', 'Cannot deliver your request at this time.' );
	}
	$body = json_decode( wp_remote_retrieve_body( $response ), true );
	$result = is_array( $body ) ? ( $body['message'] ?? null ) : null;
	if ( ! is_array( $result ) || empty( $result['ok'] ) || wp_remote_retrieve_response_code( $response ) >= 400 ) {
		return new WP_Error( is_array( $result ) ? ( $result['code'] ?? 'DELIVERY_FAILED' ) : 'DELIVERY_FAILED',
			'Cannot deliver your request at this time.' );
	}
	return $result;
}

function hasaki_crm_lead_form() {
	$retry = isset( $_GET['hsk_submission'] ) ? sanitize_text_field( wp_unslash( $_GET['hsk_submission'] ) ) : '';
	$submission = preg_match( '/^[a-f0-9-]{36}$/i', $retry ) ? $retry : wp_generate_uuid4();
	$state = isset( $_GET['hsk_state'] ) ? sanitize_key( $_GET['hsk_state'] ) : '';
	ob_start();
	if ( 'sent' === $state ) {
		echo '<p role="status">Đã tiếp nhận yêu cầu tư vấn của bạn.</p>';
	} elseif ( 'error' === $state ) {
		echo '<p role="alert">Chưa gửi được yêu cầu. Vui lòng kiểm tra thông tin và thử lại.</p>';
	}
	?>
	<form id="hasaki-crm-lead-form" method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
		<input type="hidden" name="action" value="hasaki_submit_lead">
		<input type="hidden" name="submission_id" value="<?php echo esc_attr( $submission ); ?>">
		<?php wp_nonce_field( 'hasaki_submit_lead', 'hasaki_nonce' ); ?>
		<p><label>Tên <input name="first_name" required maxlength="140" autocomplete="given-name"></label></p>
		<p><label>Họ <input name="last_name" maxlength="140" autocomplete="family-name"></label></p>
		<p><label>Điện thoại <input name="phone" type="tel" required maxlength="32" autocomplete="tel"></label></p>
		<p><label>Email <input name="email" type="email" maxlength="140" autocomplete="email"></label></p>
		<p><label>Nội dung tư vấn <textarea name="message" required maxlength="10000"></textarea></label></p>
		<p><label><input name="consent" type="checkbox" value="1" required> Tôi đồng ý cung cấp thông tin để được tư vấn.</label></p>
		<div hidden aria-hidden="true"><label>Website <input name="contact_website" tabindex="-1" autocomplete="off"></label></div>
		<button class="hsk-button" type="submit">Gửi yêu cầu tư vấn</button>
	</form>
	<?php
	return ob_get_clean();
}

function hasaki_crm_handle_lead() {
	if ( 'POST' !== ( $_SERVER['REQUEST_METHOD'] ?? '' ) ) {
		wp_die( 'Method not allowed.', '', array( 'response' => 405 ) );
	}
	check_admin_referer( 'hasaki_submit_lead', 'hasaki_nonce' );
	$submission = isset( $_POST['submission_id'] ) ? sanitize_text_field( wp_unslash( $_POST['submission_id'] ) ) : '';
	if ( ! preg_match( '/^[a-f0-9-]{36}$/i', $submission ) || ! empty( $_POST['contact_website'] ) ) {
		wp_die( 'Invalid request.', '', array( 'response' => 400 ) );
	}
	// Bound automated submissions without storing raw IPs or form contents.
	$bucket = 'hasaki_form_' . hash_hmac( 'sha256', $_SERVER['REMOTE_ADDR'] ?? '', wp_salt( 'nonce' ) );
	$count = (int) get_transient( $bucket );
	if ( $count >= 10 ) {
		wp_die( 'Vui lòng thử lại sau.', '', array( 'response' => 429 ) );
	}
	set_transient( $bucket, $count + 1, MINUTE_IN_SECONDS );
	$payload = array( 'submission_id' => $submission );
	foreach ( array( 'first_name', 'last_name', 'phone', 'email', 'message' ) as $field ) {
		$value = isset( $_POST[ $field ] ) && is_string( $_POST[ $field ] ) ? wp_unslash( $_POST[ $field ] ) : '';
		$payload[ $field ] = 'message' === $field ? sanitize_textarea_field( $value ) : sanitize_text_field( $value );
	}
	$payload['consent'] = isset( $_POST['consent'] ) && '1' === $_POST['consent'];
	$result = hasaki_crm_send_lead( $payload );
	$redirect = remove_query_arg( array( 'hsk_state', 'hsk_submission' ), wp_get_referer() ?: home_url( '/' ) );
	$args = array( 'hsk_state' => is_wp_error( $result ) ? 'error' : 'sent' );
	if ( is_wp_error( $result ) ) {
		$args['hsk_submission'] = $submission;
	}
	wp_safe_redirect( add_query_arg( $args, $redirect ), 303 );
	exit;
}

/** Synchronize exactly two owned WooCommerce webhooks; preserve other webhooks. */
function hasaki_crm_sync_webhooks() {
	if ( ! class_exists( 'WC_Webhook' ) || ! class_exists( 'WC_Data_Store' ) ) {
		return new WP_Error( 'WOO_UNAVAILABLE', 'WooCommerce must already be installed and active.' );
	}
	$secret = hasaki_crm_setting( 'HASAKI_WC_WEBHOOK_SECRET' );
	if ( ! $secret || ! hasaki_crm_base_url() ) {
		return new WP_Error( 'NOT_CONFIGURED', 'Configure the existing CRM and webhook secret first.' );
	}
	$delivery_url = hasaki_crm_base_url() . '/api/method/hasaki_integration.woocommerce.receive_order';
	$store = WC_Data_Store::load( 'webhook' );
	$ids = $store->search_webhooks( array( 'limit' => -1 ) );
	$registered = array();
	foreach ( array( 'order.created', 'order.updated' ) as $topic ) {
		$matches = array();
		foreach ( $ids as $id ) {
			$existing = new WC_Webhook( $id );
			if ( $existing->get_delivery_url() === $delivery_url && $existing->get_topic() === $topic ) {
				$matches[] = $existing;
			}
		}
		if ( count( $matches ) > 1 ) {
			return new WP_Error( 'CONFLICT', 'Duplicate webhook configuration requires review.' );
		}
		$webhook = $matches ? $matches[0] : new WC_Webhook();
		$webhook->set_name( 'Hasaki CRM - ' . $topic );
		$webhook->set_topic( $topic );
		$webhook->set_delivery_url( $delivery_url );
		$webhook->set_secret( $secret );
		$webhook->set_user_id( get_current_user_id() );
		$webhook->set_api_version( 'wp_api_v3' );
		$webhook->set_status( 'active' );
		$webhook->save();
		$registered[ $topic ] = $webhook->get_id();
	}
	return $registered;
}

function hasaki_crm_is_configured_target( $url ) {
	$base = hasaki_crm_base_url();
	return $base && in_array( $url, array(
		$base . '/api/method/hasaki_integration.wordpress.receive_lead',
		$base . '/api/method/hasaki_integration.woocommerce.receive_order',
	), true );
}

// Local Docker/host addresses and port 8000 are allowed only for the exact
// configured CRM methods. TLS verification remains enabled.
add_filter( 'http_request_host_is_external', function ( $external, $host, $url ) {
	return hasaki_crm_is_configured_target( $url ) ? true : $external;
}, 10, 3 );
add_filter( 'http_allowed_safe_ports', function ( $ports, $host, $url ) {
	if ( hasaki_crm_is_configured_target( $url ) ) {
		$port = wp_parse_url( $url, PHP_URL_PORT );
		if ( $port ) {
			$ports[] = $port;
		}
	}
	return array_unique( $ports );
}, 10, 3 );
add_filter( 'woocommerce_webhook_http_args', function ( $args, $arg, $webhook_id ) {
	$webhook = new WC_Webhook( $webhook_id );
	if ( hasaki_crm_is_configured_target( $webhook->get_delivery_url() ) ) {
		$args['headers']['X-Frappe-Site-Name'] = hasaki_crm_setting( 'HASAKI_CRM_SITE', 'crm.localhost' );
	}
	return $args;
}, 10, 3 );

add_shortcode( 'hasaki_lead_form', 'hasaki_crm_lead_form' );
add_action( 'admin_post_hasaki_submit_lead', 'hasaki_crm_handle_lead' );
add_action( 'admin_post_nopriv_hasaki_submit_lead', 'hasaki_crm_handle_lead' );

// Reuse the existing Hasaki theme's support dialog without modifying theme
// files or replacing a page. The shortcode remains usable in other layouts.
add_action( 'wp_footer', function () {
	if ( 'flatsome-hasaki-child' !== get_stylesheet() || ! hasaki_crm_base_url() ) {
		return;
	}
	echo '<template id="hasaki-crm-support-form">' . hasaki_crm_lead_form() . '</template>';
	?>
	<script>
	(() => {
		const support = document.getElementById('hsk-support');
		const template = document.getElementById('hasaki-crm-support-form');
		if (!support || !template) return;
		support.append(template.content.cloneNode(true));
		template.remove();
		if (new URLSearchParams(location.search).has('hsk_state') && !support.open) support.showModal();
	})();
	</script>
	<?php
}, 30 );

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	WP_CLI::add_command( 'hasaki-crm sync-webhooks', function () {
		if ( ! current_user_can( 'manage_woocommerce' ) ) {
			WP_CLI::error( 'Run with an existing WooCommerce administrator using --user.' );
		}
		$result = hasaki_crm_sync_webhooks();
		if ( is_wp_error( $result ) ) {
			WP_CLI::error( $result->get_error_message() );
		}
		WP_CLI::success( wp_json_encode( $result ) );
	} );
}
