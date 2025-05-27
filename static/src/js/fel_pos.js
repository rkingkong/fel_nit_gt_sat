odoo.define('fel_guatemala.pos', function (require) {
"use strict";

var models = require('point_of_sale.models');
var screens = require('point_of_sale.screens');
var gui = require('point_of_sale.gui');
var core = require('web.core');
var PopupWidget = require('point_of_sale.popups');
var rpc = require('web.rpc');

var QWeb = core.qweb;
var _t = core._t;

// Load FEL document types
models.load_models({
    model: 'fel.document.type',
    fields: ['id', 'name', 'code', 'is_invoice', 'description'],
    loaded: function(self, fel_document_types) {
        self.fel_document_types = fel_document_types;
        self.fel_document_types_by_id = {};
        for (var i = 0; i < fel_document_types.length; i++) {
            self.fel_document_types_by_id[fel_document_types[i].id] = fel_document_types[i];
        }
    },
});

// Load waiters (users with POS access)
models.load_models({
    model: 'res.users',
    fields: ['id', 'name'],
    domain: [['groups_id', 'in', [models.load_models.models[0].group_pos_user_id]]],
    loaded: function(self, waiters) {
        self.waiters = waiters;
    },
});

// Extend Order model for FEL
var _super_order = models.Order.prototype;
models.Order = models.Order.extend({
    initialize: function(attr, options) {
        _super_order.initialize.call(this, attr, options);
        this.customer_nit = this.customer_nit || '';
        this.customer_name = this.customer_name || '';
        this.table_number = this.table_number || '';
        this.waiter_id = this.waiter_id || null;
        this.waiter_name = this.waiter_name || '';
        this.fel_document_type_id = this.fel_document_type_id || null;
        this.fel_status = this.fel_status || 'draft';
        this.fel_uuid = this.fel_uuid || '';
        this.fel_error_message = this.fel_error_message || '';
    },

    init_from_JSON: function(json) {
        _super_order.init_from_JSON.apply(this, arguments);
        this.customer_nit = json.customer_nit || '';
        this.customer_name = json.customer_name || '';
        this.table_number = json.table_number || '';
        this.waiter_id = json.waiter_id || null;
        this.waiter_name = json.waiter_name || '';
        this.fel_document_type_id = json.fel_document_type_id || null;
        this.fel_status = json.fel_status || 'draft';
        this.fel_uuid = json.fel_uuid || '';
        this.fel_error_message = json.fel_error_message || '';
    },

    export_as_JSON: function() {
        var json = _super_order.export_as_JSON.apply(this, arguments);
        json.customer_nit = this.customer_nit;
        json.customer_name = this.customer_name;
        json.table_number = this.table_number;
        json.waiter_id = this.waiter_id;
        json.waiter_name = this.waiter_name;
        json.fel_document_type_id = this.fel_document_type_id;
        json.fel_status = this.fel_status;
        json.fel_uuid = this.fel_uuid;
        json.fel_error_message = this.fel_error_message;
        return json;
    },

    set_customer_info: function(nit, name) {
        this.customer_nit = nit || '';
        this.customer_name = name || '';
        this.trigger('change', this);
    },

    set_table_info: function(table_number, waiter_id, waiter_name) {
        this.table_number = table_number || '';
        this.waiter_id = waiter_id;
        this.waiter_name = waiter_name || '';
        this.trigger('change', this);
    },

    set_fel_document_type: function(doc_type_id) {
        this.fel_document_type_id = doc_type_id;
        this.trigger('change', this);
    },

    get_fel_status_color: function() {
        var status_colors = {
            'draft': 'secondary',
            'generating': 'info',
            'sending': 'warning',
            'certified': 'success',
            'error': 'danger',
            'cancelled': 'dark'
        };
        return status_colors[this.fel_status] || 'secondary';
    },

    get_fel_status_text: function() {
        var status_texts = {
            'draft': _t('Draft'),
            'generating': _t('Generating'),
            'sending': _t('Sending'),
            'certified': _t('Certified'),
            'error': _t('Error'),
            'cancelled': _t('Cancelled')
        };
        return status_texts[this.fel_status] || _t('Unknown');
    },

    can_send_to_fel: function() {
        return (
            this.pos.config.use_fel &&
            this.is_paid() &&
            this.fel_status in ['draft', 'error'] &&
            (this.customer_nit || this.pos.config.fel_allow_cf)
        );
    },

    requires_fel: function() {
        return this.pos.config.use_fel && this.is_paid();
    },
});

// FEL Customer Information Popup
var FelCustomerPopup = PopupWidget.extend({
    template: 'FelCustomerPopup',

    init: function(parent, args) {
        this._super(parent, args);
        this.options = args.options || {};
        this.order = this.options.order || this.pos.get_order();
        this.waiters = this.pos.waiters || [];
        
        // Initialize with current order data
        this.nit = this.order.customer_nit || '';
        this.customer_name = this.order.customer_name || '';
        this.table_number = this.order.table_number || '';
        this.waiter_id = this.order.waiter_id || null;
    },

    show: function(options) {
        this._super(options);
        var self = this;
        
        // Set up event handlers
        this.$('#customer-nit').on('change', function() {
            self.nit = $(this).val();
            self.auto_fill_customer_info();
        });

        this.$('#customer-name').on('change', function() {
            self.customer_name = $(this).val();
        });

        this.$('#table-number').on('change', function() {
            self.table_number = $(this).val();
        });

        this.$('#waiter-select').on('change', function() {
            self.waiter_id = parseInt($(this).val()) || null;
        });
    },

    auto_fill_customer_info: function() {
        var self = this;
        
        if (this.nit === 'CF' || this.nit.toLowerCase() === 'cf') {
            this.$('#customer-name').val('Consumidor Final');
            this.customer_name = 'Consumidor Final';
            return;
        }

        // Search for existing customer
        if (this.nit && this.nit.length >= 8) {
            // You could add NIT verification here
            console.log('Searching for customer with NIT:', this.nit);
        }
    },

    confirm: function() {
        var waiter_name = '';
        if (this.waiter_id) {
            var waiter = this.waiters.find(w => w.id === this.waiter_id);
            waiter_name = waiter ? waiter.name : '';
        }

        // Set customer information
        this.order.set_customer_info(this.nit, this.customer_name);
        this.order.set_table_info(this.table_number, this.waiter_id, waiter_name);

        // Auto-set document type based on customer
        this.auto_set_document_type();

        this.gui.close_popup();
        
        if (this.options.confirm) {
            this.options.confirm.call(this);
        }
    },

    auto_set_document_type: function() {
        // Set default document type based on customer
        var doc_types = this.pos.fel_document_types;
        var default_type = null;

        if (this.nit === 'CF' || !this.nit) {
            // Consumidor Final - use FACT
            default_type = doc_types.find(dt => dt.code === 'FACT');
        } else {
            // For other customers, you could determine based on tax regime
            // For now, default to FACT
            default_type = doc_types.find(dt => dt.code === 'FACT');
        }

        if (default_type) {
            this.order.set_fel_document_type(default_type.id);
        }
    },
});

gui.define_popup({name:'fel_customer_popup', widget: FelCustomerPopup});

// FEL Document Type Popup
var FelDocumentTypePopup = PopupWidget.extend({
    template: 'FelDocumentTypePopup',

    init: function(parent, args) {
        this._super(parent, args);
        this.options = args.options || {};
        this.order = this.options.order || this.pos.get_order();
        this.document_types = this.pos.fel_document_types.filter(dt => dt.is_invoice);
        this.selected_type_id = this.order.fel_document_type_id;
    },

    selectDocumentType: function(event) {
        this.selected_type_id = parseInt($(event.currentTarget).data('id'));
        this.$('.document-type-option').removeClass('selected');
        $(event.currentTarget).addClass('selected');
    },

    confirm: function() {
        if (this.selected_type_id) {
            this.order.set_fel_document_type(this.selected_type_id);
        }
        this.gui.close_popup();
        
        if (this.options.confirm) {
            this.options.confirm.call(this);
        }
    },
});

gui.define_popup({name:'fel_document_type_popup', widget: FelDocumentTypePopup});

// FEL Send Confirmation Popup
var FelSendConfirmationPopup = PopupWidget.extend({
    template: 'FelSendConfirmationPopup',

    init: function(parent, args) {
        this._super(parent, args);
        this.options = args.options || {};
        this.order = this.options.order || this.pos.get_order();
    },

    formatCurrency: function(amount) {
        return this.pos.format_currency(amount);
    },

    confirm: function() {
        this.gui.close_popup();
        this.send_order_to_fel();
    },

    send_order_to_fel: function() {
        var self = this;
        var order = this.order;

        // Show loading
        this.gui.show_popup('loading', {
            title: _t('Sending to FEL'),
            body: _t('Please wait while we send your order to FEL...'),
        });

        // Call backend to send order to FEL
        rpc.query({
            model: 'pos.order',
            method: 'send_to_fel',
            args: [[order.server_id]], // Use server ID of the order
        }).then(function(result) {
            self.gui.close_popup(); // Close loading popup

            if (result && result.params && result.params.type === 'success') {
                // Update order status
                order.fel_status = 'certified';
                order.fel_uuid = result.uuid || '';
                
                // Show success notification
                self.gui.show_popup('fel_success_notification', {
                    order_name: order.name,
                    uuid: order.fel_uuid,
                });
            } else {
                // Show error
                var error_msg = result && result.params ? result.params.message : _t('Unknown error occurred');
                order.fel_status = 'error';
                order.fel_error_message = error_msg;
                
                self.gui.show_popup('fel_error_notification', {
                    error_message: error_msg,
                });
            }
        }).catch(function(error) {
            self.gui.close_popup(); // Close loading popup
            
            order.fel_status = 'error';
            order.fel_error_message = error.message || _t('Connection error');
            
            self.gui.show_popup('fel_error_notification', {
                error_message: error.message || _t('Failed to connect to FEL service'),
            });
        });
    },
});

gui.define_popup({name:'fel_send_confirmation_popup', widget: FelSendConfirmationPopup});

// FEL Success Notification
var FelSuccessNotification = PopupWidget.extend({
    template: 'FelSuccessNotification',
    
    init: function(parent, args) {
        this._super(parent, args);
        this.options = args.options || {};
        this.order_name = this.options.order_name || '';
        this.uuid = this.options.uuid || '';
    },
});

gui.define_popup({name:'fel_success_notification', widget: FelSuccessNotification});

// FEL Error Notification  
var FelErrorNotification = PopupWidget.extend({
    template: 'FelErrorNotification',
    
    init: function(parent, args) {
        this._super(parent, args);
        this.options = args.options || {};
        this.error_message = this.options.error_message || _t('An error occurred');
    },
});

gui.define_popup({name:'fel_error_notification', widget: FelErrorNotification});

// Extend Payment Screen for FEL
var PaymentScreenWidget = screens.PaymentScreenWidget;
screens.PaymentScreenWidget = screens.PaymentScreenWidget.extend({
    
    init: function(parent, options) {
        this._super(parent, options);
    },

    validate_order: function(force_validation) {
        var self = this;
        var order = this.pos.get_order();
        
        // If FEL is required and not configured, show customer popup first
        if (order.requires_fel() && !order.customer_nit && this.pos.config.fel_require_customer) {
            this.gui.show_popup('fel_customer_popup', {
                order: order,
                confirm: function() {
                    // After setting customer info, continue with validation
                    PaymentScreenWidget.prototype.validate_order.call(self, force_validation);
                }
            });
            return;
        }

        // Continue with normal validation
        return this._super(force_validation);
    },

    finalize_validation: function() {
        var self = this;
        var order = this.pos.get_order();
        
        // Call parent finalize_validation first
        this._super();

        // After order is finalized, offer to send to FEL if auto-generate is disabled
        if (order.requires_fel() && !this.pos.config.fel_auto_generate && order.can_send_to_fel()) {
            setTimeout(function() {
                self.gui.show_popup('confirm', {
                    title: _t('Send to FEL?'),
                    body: _t('Do you want to send this order to FEL now?'),
                    confirm: function() {
                        self.gui.show_popup('fel_send_confirmation_popup', {
                            order: order
                        });
                    }
                });
            }, 1000); // Delay to allow order processing to complete
        }
    },
});

// Add FEL Control Button
var FelControlButton = screens.ActionButtonWidget.extend({
    template: 'FelControlButton',

    button_click: function() {
        var order = this.pos.get_order();
        this.gui.show_popup('fel_customer_popup', {
            order: order
        });
    },
});

screens.define_action_button({
    'name': 'fel_customer_info',
    'widget': FelControlButton,
    'condition': function() {
        return this.pos.config.use_fel;
    },
});

// Extend Receipt Screen for FEL information
var ReceiptScreenWidget = screens.ReceiptScreenWidget;
screens.ReceiptScreenWidget = screens.ReceiptScreenWidget.extend({
    
    get_receipt_render_env: function() {
        var env = this._super();
        var order = this.pos.get_order();
        
        // Add FEL information to receipt environment
        env.fel_info = {
            customer_nit: order.customer_nit || '',
            customer_name: order.customer_name || '',
            table_number: order.table_number || '',
            waiter_name: order.waiter_name || '',
            fel_status: order.fel_status || '',
            fel_uuid: order.fel_uuid || '',
            fel_status_text: order.get_fel_status_text(),
            requires_fel: order.requires_fel(),
            show_fel_info: this.pos.config.use_fel && order.requires_fel()
        };
        
        return env;
    },
});

// Extend PosModel for FEL configuration
var PosModelSuper = models.PosModel.prototype;
models.PosModel = models.PosModel.extend({
    
    initialize: function(session, attributes) {
        // Load FEL configuration
        this.fel_config = null;
        return PosModelSuper.initialize.call(this, session, attributes);
    },

    after_load_server_data: function() {
        var self = this;
        return PosModelSuper.after_load_server_data.call(this).then(function() {
            // Load FEL configuration if FEL is enabled
            if (self.config.use_fel) {
                return self.load_fel_config();
            }
        });
    },

    load_fel_config: function() {
        var self = this;
        return rpc.query({
            model: 'fel.config',
            method: 'get_active_config',
            args: [this.company.id],
        }).then(function(fel_config) {
            self.fel_config = fel_config;
        }).catch(function(error) {
            console.warn('Could not load FEL configuration:', error);
        });
    },

    // Auto-send orders to FEL if configured
    push_order: function(order, opts) {
        var self = this;
        var pushed = PosModelSuper.push_order.call(this, order, opts);
        
        if (this.config.use_fel && this.config.fel_auto_generate && order.requires_fel()) {
            pushed.then(function(server_ids) {
                if (server_ids && server_ids.length > 0) {
                    // Auto-send to FEL
                    self.auto_send_order_to_fel(server_ids[0], order);
                }
            });
        }
        
        return pushed;
    },

    auto_send_order_to_fel: function(server_id, order) {
        var self = this;
        
        // Only auto-send if order has required customer info
        if (!order.customer_nit && !this.config.fel_allow_cf) {
            console.log('Skipping auto FEL send - no customer NIT');
            return;
        }

        console.log('Auto-sending order to FEL:', server_id);
        
        rpc.query({
            model: 'pos.order',
            method: 'send_to_fel',
            args: [[server_id]],
        }).then(function(result) {
            if (result && result.params && result.params.type === 'success') {
                console.log('Order auto-sent to FEL successfully');
                // Update local order status
                order.fel_status = 'certified';
                order.fel_uuid = result.uuid || '';
            } else {
                console.warn('Auto FEL send failed:', result);
                order.fel_status = 'error';
            }
        }).catch(function(error) {
            console.error('Auto FEL send error:', error);
            order.fel_status = 'error';
        });
    },
});

// Restaurant Table Widget (if restaurant module is active)
if (screens.RestaurantTableWidget) {
    var RestaurantTableWidget = screens.RestaurantTableWidget;
    screens.RestaurantTableWidget = screens.RestaurantTableWidget.extend({
        
        get_table_render_env: function() {
            var env = this._super();
            var orders = this.pos.get_table_orders(this.table);
            
            // Add FEL status information
            env.fel_status_summary = this.get_fel_status_summary(orders);
            
            return env;
        },

        get_fel_status_summary: function(orders) {
            var summary = {
                total_orders: orders.length,
                fel_certified: 0,
                fel_pending: 0,
                fel_errors: 0
            };

            orders.forEach(function(order) {
                if (order.fel_status === 'certified') {
                    summary.fel_certified++;
                } else if (order.fel_status === 'error') {
                    summary.fel_errors++;
                } else if (order.requires_fel()) {
                    summary.fel_pending++;
                }
            });

            return summary;
        },
    });
}

// Add CSS classes for FEL styling
$(document).ready(function() {
    // Add custom CSS for FEL components
    var fel_css = `
        <style>
        .fel-customer-popup .popup-body {
            padding: 20px;
        }
        
        .fel-customer-popup .form-group {
            margin-bottom: 15px;
        }
        
        .fel-customer-popup label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        
        .fel-status-widget .badge {
            font-size: 12px;
            padding: 4px 8px;
        }
        
        .fel-document-type-popup .document-types {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .fel-document-type-popup .document-type-option {
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s;
        }
        
        .fel-document-type-popup .document-type-option:hover {
            border-color: #007bff;
            background-color: #f8f9fa;
        }
        
        .fel-document-type-popup .document-type-option.selected {
            border-color: #007bff;
            background-color: #e3f2fd;
        }
        
        .fel-document-type-popup .type-code {
            font-size: 18px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 5px;
        }
        
        .fel-document-type-popup .type-name {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .fel-document-type-popup .type-description {
            font-size: 12px;
            color: #666;
        }
        
        .fel-send-popup .order-details {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }
        
        .fel-success .notification-icon {
            color: #28a745;
            font-size: 24px;
        }
        
        .fel-error .notification-icon {
            color: #dc3545;
            font-size: 24px;
        }
        
        .notification {
            display: flex;
            align-items: center;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }
        
        .notification.fel-success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        
        .notification.fel-error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        
        .notification-icon {
            margin-right: 15px;
        }
        
        .notification-content h4 {
            margin: 0 0 5px 0;
        }
        
        .notification-content p {
            margin: 0;
        }
        
        .control-button.fel-button {
            background-color: #17a2b8;
            color: white;
        }
        
        .control-button.fel-button:hover {
            background-color: #138496;
        }
        
        .table-widget {
            position: relative;
            min-height: 80px;
            border-radius: 8px;
            padding: 10px;
            margin: 5px;
            background: white;
            border: 2px solid #ddd;
            text-align: center;
        }
        
        .table-widget .table-number {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .table-widget .table-status.status-available {
            color: #28a745;
        }
        
        .table-widget .table-status.status-occupied {
            color: #dc3545;
        }
        
        .table-widget .table-waiter {
            position: absolute;
            bottom: 5px;
            left: 5px;
            right: 5px;
            font-size: 10px;
            color: #666;
        }
        </style>
    `;
    
    $('head').append(fel_css);
});

// Export the module
return {
    FelCustomerPopup: FelCustomerPopup,
    FelDocumentTypePopup: FelDocumentTypePopup,
    FelSendConfirmationPopup: FelSendConfirmationPopup,
    FelSuccessNotification: FelSuccessNotification,
    FelErrorNotification: FelErrorNotification,
    FelControlButton: FelControlButton,
};

});
