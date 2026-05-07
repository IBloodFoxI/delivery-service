'use strict';

/* ===== Add to Cart (AJAX) ===== */
document.addEventListener('DOMContentLoaded', function () {

    // Add-to-cart buttons on catalog page
    document.querySelectorAll('.btn-add-cart').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const productId = btn.dataset.productId;
            const csrfToken = getCookie('csrftoken');

            fetch('/orders/cart/add/' + productId + '/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'quantity=1',
            })
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    btn.classList.add('added');
                    btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>В корзине';
                    btn.disabled = true;

                    // Update cart badge in navbar
                    const badge = document.getElementById('cart-badge');
                    if (badge && data.cart_count !== undefined) {
                        badge.textContent = data.cart_count;
                        badge.style.display = data.cart_count > 0 ? '' : 'none';
                    }
                }
            })
            .catch(function () {
                // Fallback: redirect to add-to-cart URL
                window.location.href = '/orders/cart/add/' + productId + '/';
            });
        });
    });

    /* ===== Balance top-up: clickable preset amounts ===== */
    document.querySelectorAll('.topup-amount-card').forEach(function (card) {
        card.addEventListener('click', function () {
            const amount = card.dataset.amount;
            const input = document.getElementById('topup-custom');
            if (input) {
                input.value = amount;
            }
            document.querySelectorAll('.topup-amount-card').forEach(function (c) {
                c.classList.remove('selected');
            });
            card.classList.add('selected');
        });
    });

    /* ===== Auto-dismiss alerts after 4 s ===== */
    document.querySelectorAll('.alert-auto-dismiss').forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 4000);
    });

    /* ===== Confirm before cancel/delete forms ===== */
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(el.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });
});

/* ===== Cookie helper ===== */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(function (cookie) {
            const c = cookie.trim();
            if (c.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(c.slice(name.length + 1));
            }
        });
    }
    return cookieValue;
}
