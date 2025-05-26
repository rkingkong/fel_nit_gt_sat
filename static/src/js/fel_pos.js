odoo.define('fel_guatemala.pos', function (require) {
"use strict";

var models = require('point_of_sale.models');
var screens = require('point_of_sale.screens');
var gui = require('point_of_sale.gui');
var core = require('web.core');
var PopupWidget = require('point_of_sale.popups');

var QWeb = core.qweb;
var _t = core._t;

// Load FEL document types
models.load_models({
    model: 'fel.document.type',
    fields: ['id', 'name', 'code', 'is_invoice'],
    loaded: function(self, fel_document_types) {
        self.fel_document_types = fel_document_types;
        self.fel_document_types_by_id = {};
        for (var i = 0; i < fel_document_types.length; i++) {
            self.fel_document_types_by_id[fel_document_types[i].id] = fel_document_types[i];
        }
    },
});

// Extend Order model for FEL
var _super_order = models.Order.prototype;
models.Order = models.Order.extend({
    initialize: function(attr, options) {
        _super_order.initialize.call(this, attr, options);
        this.customer_nit = this.customer_nit || '';
        this.fel_document_type_id = this.fel_document_type_i
