

/** @odoo-module **/
import { jsonrpc } from "@web/core/network/rpc_service";
//odoo.define('dev_helpdesk_tracking.web_portal', function (require) {
//'use strict';
//    require('web.dom_ready');
//    var ajax = require('web.ajax');
//import { jsonrpc } from "@web/core/network/rpc_service";



if($('.tracking-input-container').length){
    $(".confirm_track_do").click(function () {
//        alert("I am an alert box bb!");
        var tracking_number = $('.tracking-number-input').val();
        if(!tracking_number){
            alert("Enter Warranty Number");
        }
        jsonrpc("/dev_warranty_track", {
            'do_no':tracking_number
        },{'async':false}).then(function(res){
            	if(res){
            		$('.dev-tracking-container').removeClass('d-none');
            		$('.warranty-status').text(res.status)
            		$('.customer-warranty-status').text(res.customer)
            		$('.warranty-start-date').text(res.start_date)
            		$('.warranty-end-date').text(res.end_date)
            		$('.warranty-sale-order').text(res.sale_order)
            		$('.dev-none-tracking-container').addClass('d-none');
            	}
            	if(!res){
            	    $('.dev-tracking-container').addClass('d-none');
            	    $('.dev-none-tracking-container').removeClass('d-none');
            	}        });

    });
}

    
//});
