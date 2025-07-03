odoo.define('fel_nit_gt_sat.pos', function (require) {
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
    },
    
    export_as_JSON: function() {
        var json = _super_order.export_as_JSON.apply(this, arguments);
        json.customer_nit = this.customer_nit;
        json.customer_name = this.customer_name;
        json.table_number = this.table_number;
        json.waiter_id = this.waiter_id;
        json.waiter_name = this.waiter_name;
        json.fel_document_type_id = this.fel_document_type_id;
        return json;
    },
    
    init_from_JSON: function(json) {
        _super_order.init_from_JSON.apply(this, arguments);
        this.customer_nit = json.customer_nit;
        this.customer_name = json.customer_name;
        this.table_number = json.table_number;
        this.waiter_id = json.waiter_id;
        this.waiter_name = json.waiter_name;
        this.fel_document_type_id = json.fel_document_type_id;
    },
    
    set_customer_nit: function(nit) {
        this.customer_nit = nit || 'CF';
    },
    
    set_customer_name: function(name) {
        this.customer_name = name || 'Consumidor Final';
    },
    
    set_table_number: function(table) {
        this.table_number = table;
    },
    
    set_waiter: function(waiter_id, waiter_name) {
        this.waiter_id = waiter_id;
        this.waiter_name = waiter_name;
    }
});

// FEL Customer Info Popup
var FelCustomerPopupWidget = PopupWidget.extend({
    template: 'FelCustomerPopupWidget',
    
    show: function(options) {
        options = options || {};
        this._super(options);
        
        var order = this.pos.get_order();
        this.$('.customer-nit').val(order.customer_nit || '');
        this.$('.customer-name').val(order.customer_name || '');
        
        // Focus on NIT input
        this.$('.customer-nit').focus();
    },
    
    click_confirm: function() {
        var order = this.pos.get_order();
        var nit = this.$('.customer-nit').val() || 'CF';
        var name = this.$('.customer-name').val() || 'Consumidor Final';
        
        // Special handling for CF
        if (nit.toUpperCase() === 'CF') {
            nit = 'CF';
            name = name || 'Consumidor Final';
        }
        
        order.set_customer_nit(nit);
        order.set_customer_name(name);
        
        // Verify NIT if not CF
        if (nit !== 'CF' && this.options.verify_nit) {
            this.verify_nit(nit);
        }
        
        this.gui.close_popup();
    },
    
    verify_nit: function(nit) {
        var self = this;
        
        rpc.query({
            model: 'fel.nit.verification.service',
            method: 'verify_nit_from_pos',
            args: [nit],
        }).then(function(result) {
            if (result.verified) {
                self.gui.show_popup('alert', {
                    title: _t('NIT Verified'),
                    body: _t('NIT: ') + nit + '\n' + 
                          _t('Name: ') + result.name + '\n' +
                          _t('Regime: ') + result.regime,
                });
            } else {
                self.gui.show_popup('alert', {
                    title: _t('NIT Verification Failed'),
                    body: result.message,
                });
            }
        }).catch(function(error) {
            self.gui.show_popup('error', {
                title: _t('NIT Verification Error'),
                body: _t('Could not verify NIT. Please check your connection.'),
            });
        });
    }
});

gui.define_popup({name: 'fel-customer', widget: FelCustomerPopupWidget});

// Restaurant Waiter Selection
var WaiterSelectionPopupWidget = PopupWidget.extend({
    template: 'WaiterSelectionPopupWidget',
    
    show: function(options) {
        options = options || {};
        this._super(options);
        this.render_waiters();
    },
    
    render_waiters: function() {
        var self = this;
        var waiters = this.pos.waiters || [];
        var $list = this.$('.waiter-list');
        
        $list.empty();
        
        waiters.forEach(function(waiter) {
            var $waiter = $('<div class="waiter-item">').text(waiter.name);
            $waiter.data('waiter-id', waiter.id);
            $waiter.click(function() {
                self.select_waiter(waiter.id, waiter.name);
            });
            $list.append($waiter);
        });
    },
    
    select_waiter: function(waiter_id, waiter_name) {
        var order = this.pos.get_order();
        order.set_waiter(waiter_id, waiter_name);
        this.gui.close_popup();
        
        // Show confirmation
        this.gui.show_popup('alert', {
            title: _t('Waiter Selected'),
            body: _t('Waiter: ') + waiter_name,
        });
    }
});

gui.define_popup({name: 'waiter-selection', widget: WaiterSelectionPopupWidget});

// Extend Payment Screen for FEL
screens.PaymentScreenWidget.include({
    
    validate_order: function(force_validation) {
        var self = this;
        var order = this.pos.get_order();
        
        // Check if FEL is required
        if (this.pos.config.use_fel && !order.customer_nit) {
            // Show customer info popup before payment
            this.gui.show_popup('fel-customer', {
                title: _t('Customer Information for FEL'),
                confirm: function() {
                    self._super(force_validation);
                }
            });
        } else {
            this._super(force_validation);
        }
    },
    
    finalize_validation: function() {
        var self = this;
        var order = this.pos.get_order();
        
        // If auto-generate FEL is enabled, send to FEL after payment
        if (this.pos.config.use_fel && this.pos.config.fel_auto_generate) {
            this._super();
            
            // Send order to FEL in background
            setTimeout(function() {
                self.send_order_to_fel(order);
            }, 1000);
        } else {
            this._super();
        }
    },
    
    send_order_to_fel: function(order) {
        // This would be implemented to send the order to FEL
        // For now, just log
        console.log('Sending order to FEL:', order.name);
    }
});

// Table Management Extension
if (odoo.pos_restaurant) {
    screens.TableWidget.include({
        
        click_table: function(table) {
            var self = this;
            
            // Check if waiter is required
            if (this.pos.config.require_waiter && !this.pos.get_order().waiter_id) {
                this.gui.show_popup('waiter-selection', {
                    title: _t('Select Waiter'),
                    confirm: function() {
                        self._super(table);
                    }
                });
            } else {
                this._super(table);
            }
        }
    });
}

// Action buttons for FEL
var FelActionButton = screens.ActionButtonWidget.extend({
    template: 'FelActionButton',
    
    button_click: function() {
        this.gui.show_popup('fel-customer', {
            title: _t('Set Customer Info for FEL'),
            verify_nit: true
        });
    }
});

screens.define_action_button({
    'name': 'fel_customer_info',
    'widget': FelActionButton,
    'condition': function() {
        return this.pos.config.use_fel;
    }
});

return {
    FelCustomerPopupWidget: FelCustomerPopupWidget,
    WaiterSelectionPopupWidget: WaiterSelectionPopupWidget,
    FelActionButton: FelActionButton
};

});