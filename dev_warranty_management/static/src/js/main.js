odoo.define('dev_helpdesk.main', function (require) {
"use strict";

    var AbstractAction = require('web.AbstractAction');
	var session = require('web.session');
	var rpc = require('web.rpc');
	var utils = require('web.utils');
	var Dialog = require('web.Dialog');
	var time = require('web.time');
	var datepicker = require('web.datepicker');
	var round_di = utils.round_decimals;
	var core = require('web.core');
	var QWeb = core.qweb;
	var _t = core._t;

	var InvoiceDashboard = AbstractAction.extend( {
	    title: core._t('Helpdesk Dashboard'),
	    template: 'HelpdeskeDashboardAction',
//	    contentTemplate: 'HelpdeskeDashboardAction',
	    events: {
	        'click .navigate_to': 'action_navigate_to',
	        'change .users-option': 'action_change_user_filter',
	        'change .teams-option': 'action_change_team_filter',
	        'change .partners-option': 'action_change_partner_filter',
	        'click .apply-dashboard-date-filter': '_onApplyDateFilter',
	        'click .clear-dashboard-date-filter': '_onClearDateValues',
	        'click .dev-menu-action': '_on_click_menu_action',
	        'change .date-based-filter' : '_on_change_date_based_filter',
	    },
	    init: function (parent, params) {
	        this._super(parent, params);
	    },
	    start: function () {
	        this.set("title", this.title);
	        this.init_filters();
	        this.load_invoices();
	    },
	    getContext: function () {
            var context = {
                DateFilterStartDate: this.DateFilterStartDate,
                DateFilterEndDate: this.DateFilterEndDate,
            }
            return Object.assign(context)
        },
        _on_change_date_based_filter: function(event){
        	var self = this;
        	var value = $(event.currentTarget).val();
        	if(value == 'custom_range'){
        		if (!self.StartDatePickerWidget){
    	    		this.StartDatePickerWidget = new (datepicker.DateWidget)(this);
    	        }
    	    	if (!self.EndDatePickerWidget){
    	    		this.EndDatePickerWidget = new (datepicker.DateWidget)(this);
    	        }
	    		if(self.StartDatePickerWidget){
	    			self.StartDatePickerWidget.appendTo($(".date_input_fields")).then((function () {
	            		self.StartDatePickerWidget.$el.addClass("btn_middle_child o_input");
	            		self.StartDatePickerWidget.$el.find("input").attr("placeholder", "Start Date");
	            		self.StartDatePickerWidget.on("datetime_changed", self, function () {
	                        $(".apply-dashboard-date-filter").removeClass("d-none");
	                        $(".clear-dashboard-date-filter").removeClass("d-none");
	                    });
	                }).bind(self));
	    		}
            	if(self.EndDatePickerWidget){
            		self.EndDatePickerWidget.appendTo($(".date_input_fields")).then((function () {
                		self.EndDatePickerWidget.$el.addClass("btn_middle_child o_input");
                		self.EndDatePickerWidget.$el.find("input").attr("placeholder", "End Date");
                		self.EndDatePickerWidget.on("datetime_changed", self, function () {
                            $(".apply-dashboard-date-filter").removeClass("d-none");
                            $(".clear-dashboard-date-filter").removeClass("d-none");
                        });
                    }).bind(self));
            	}
            	self.show_date_range_block();
        	} else {
        		self.hide_date_range_block();
        		self.load_invoices();
        	}
        },
        show_date_range_block: function(){
        	$('.date_input_fields').show();
        	$('.apply-dashboard-date-filter').removeClass('d-none');
        	$('.clear-dashboard-date-filter').removeClass('d-none');
        },
        hide_date_range_block: function(){
        	$('.date_input_fields').attr("style", "display: none !important");
    		$('.apply-dashboard-date-filter').addClass('d-none');
    		$('.clear-dashboard-date-filter').addClass('d-none');
        },
        _onClearDateValues: function () {
            this.DateFilterStartDate = false;
            this.DateFilterEndDate = false;
            this.load_invoices();
            this.StartDatePickerWidget.setValue(false);
            this.EndDatePickerWidget.setValue(false);
        },
        _on_click_menu_action: function(ev){
        	var self = this;
	    	var rec_id = $(ev.currentTarget).attr('rec-id')
	    	var action_type = $(ev.currentTarget)[0].id;
	    	if(action_type == 'view'){
	    		self.do_action({
	                type: 'ir.actions.act_window',
	                res_model: 'helpdesk.ticket',
	                res_id: Number(rec_id),
	                views: [[false, 'form']],
	                target: 'current'
	            });
	    	} else if(action_type == 'send_email'){
	    		var params = {
	            		model: 'helpdesk.ticket',
	            		method: 'action_send_email_by_dashboard',
	            		args: [Number(rec_id)],
	            	}
	            	rpc.query(params)
	                .then(function(result){
	                	console.log("result?",result);
	                });
	    	} else if(action_type == "register_payment"){
	    		var $dialog = new Dialog(self, {
                    size: 'large',
                    title: _t("Register Payment"),
                    buttons: [{
    	                text: _t('Confirm'),
    	                classes: 'btn-primary',
    	                click: function () {
    	                	var journal_id = $('#journal_id').val() || false;
    	                	var payment_date = $('#payment_date_input').val() || false;
    	                	var amount = $('#payment_amount').val() || false;
    	                	if(!journal_id){
    	                		return self.do_notify('Select Payment Journal', false);
    	                	}
    	                	if (!payment_date){
    	                		return self.do_notify('Select Payment Date', false);
	                		}
    	                	if (!amount){
    	                		return self.do_notify('Enter Payment Amount', false);
    	                	}
    	                	if (amount){
    	                		if(amount == parseInt(amount)){
//    	                			alert("integer")
    	                		} else if( amount == parseFloat(amount)){
//    	                			alert("float")
    	                		} else{	
    	                			return self.do_notify('Enter Payment Amount', false);
    	                		}
    	                	}
	                		var vals = {
        						'journal_id': Number(journal_id),
        						'payment_date':payment_date,
        						'amount': parseFloat(amount),
    						}
	                		var params = {
                        		model: 'helpdesk.ticket',
                        		method: 'action_create_payment_from_dashboard',
                        		args: [Number(rec_id),vals],
                        	}
                        	rpc.query(params)
                            .then(function(result){
                            	console.log("result>>>",result);
                            	self.load_invoices();
                            });
	                		this.close(true);
    	                },
    	            }, {
    	                text: _t('Close'),
    	                close: true,
    	            }],
                    $content: QWeb.render('dev_helpdesk.CreatePayment',{'journals':self.journals}),
                }).open();
	    	}
	    	
//	    	else if(action_type == 'mark_as_done'){
//	    		var params = {
//            		model: 'mail.activity',
//            		method: 'action_activity_mark_as_done',
//            		args: [Number(rec_id)],
//            	}
//            	rpc.query(params)
//                .then(function(result){
//                	self.load_invoices();
//                });
//	    	} else if(action_type == 'done_and_schedule_next'){
//	    		var $dialog = new Dialog(self, {
//                    size: 'large',
//                    title: _t("Create Activity"),
//                    buttons: [{
//    	                text: _t('Confirm'),
//    	                classes: 'btn-primary',
//    	                click: function () {
//    	                	var activity_type = $('#activity_type_id').val() || false;
//    	                	var user_id = $('#user_id_schedule').val() || false;
//    	                	var due_date = $('#due_date_input').val() || false;
//    	                	var summary = $('summary_schedule').val() || false;
//	                		if(!activity_type){
//	                			return alert(_t('Select Activity Type'))
//	                		}
//	                		if (!user_id){
//	                			return alert(_t('Assign User to Activity'))
//	                		}
//	                		if (!due_date){
//	                			return alert(_t('Select Due Date'))
//	                		}
//	                		var vals = {
//        						'activity_type': Number(activity_type),
//        						'user_id': Number(user_id),
//        						'due_date':due_date,
//        						'summary': summary,
//    						}
//	                		var params = {
//                        		model: 'mail.activity',
//                        		method: 'action_done_and_schedule_next',
//                        		args: [Number(rec_id),vals],
//                        	}
//                        	rpc.query(params)
//                            .then(function(result){
//                            	self.load_invoices();
//                            });
//	                		this.close(true);
//    	                },
//    	            }, {
//    	                text: _t('Close'),
//    	                close: true,
//    	            }],
//                    $content: QWeb.render('dev_user_activity.ScheduleNext',{'activity_types':self.activity_types,
//                    	'users':self.users}),
//                }).open();
//	    	}
        },
	    _onApplyDateFilter: function (e) {
            var self = this;
            var start_date = self.StartDatePickerWidget.getValue();
            var end_date = self.EndDatePickerWidget.getValue();
            if (start_date === "Invalid date") {
                alert("Invalid Start Date!.")
            } else if (end_date === "Invalid date") {
                alert("Invalid End Date!.")
            } else {
                if (start_date && end_date) {
                    if (start_date <= end_date) {
                        self.DateFilterStartDate = start_date.add(-this.getSession().getTZOffset(start_date), 'minutes');
                        self.DateFilterEndDate = end_date.add(-this.getSession().getTZOffset(start_date), 'minutes');
                    	self.load_invoices();
                    } else {
                        alert(_t("Start date should be less than end date"));
                    }
                } else {
                    alert(_t("Please enter start date and end date"));
                }
            }
        },
	    init_filters: function(){
	    	var self = this;
	    	var params = {
        		model: 'helpdesk.ticket',
        		method: 'load_users_and_partners',
        		args: [],
        	}
        	rpc.query(params, {async: false})
            .then(function(result){
            	var filters = QWeb.render('ActivityFilter', {
	            	'users':result.users,
	            	'partners':result.partners,
	            	'teams':result.teams,
	            	'widget':self,
	            });
            	self.users = result
            	$('.filter-header').html(filters);
            });
//	    	if (!self.StartDatePickerWidget){
//	    		this.StartDatePickerWidget = new (datepicker.DateWidget)(this);
//	        }
//	    	if (!self.EndDatePickerWidget){
//	    		this.EndDatePickerWidget = new (datepicker.DateWidget)(this);
//	        }
//	    	setTimeout(function(){
//	    		if(self.StartDatePickerWidget){
//	    			self.StartDatePickerWidget.appendTo($(".date_input_fields")).then((function () {
//	            		self.StartDatePickerWidget.$el.addClass("btn_middle_child o_input");
//	            		self.StartDatePickerWidget.$el.find("input").attr("placeholder", "Start Date");
//	            		self.StartDatePickerWidget.on("datetime_changed", self, function () {
//	                        $(".apply-dashboard-date-filter").removeClass("d-none");
//	                        $(".clear-dashboard-date-filter").removeClass("d-none");
//	                    });
//	                }).bind(self));
//	    		}
//            	if(self.EndDatePickerWidget){
//            		self.EndDatePickerWidget.appendTo($(".date_input_fields")).then((function () {
//                		self.EndDatePickerWidget.$el.addClass("btn_middle_child o_input");
//                		self.EndDatePickerWidget.$el.find("input").attr("placeholder", "End Date");
//                		self.EndDatePickerWidget.on("datetime_changed", self, function () {
//                            $(".apply-dashboard-date-filter").removeClass("d-none");
//                            $(".clear-dashboard-date-filter").removeClass("d-none");
//                        });
//                    }).bind(self));
//            	}
//        	}, 500);
	    },
	    get_report_url: function(id){
	    	var url = "/dashboard/invoices/"+Number(id)+"?report_type=pdf&amp;download=true";
	    	return url;
	    },
	    load_invoices: function(){
	    	var self = this;
	    	var args = [];
	    	var vals = {};
    	     var team_id = $('.teams-option').val();
	    	 var user_id = $('.users-option').val();
	    	 var partner_id = $('.partners-option').val();
             if(Number(user_id) > 0){
            	 vals['user_id'] = user_id;
	    	}
            if(Number(partner_id) > 0){
            	 vals['partner_id'] = partner_id;
	    	}
	    	if(Number(team_id) > 0){
            	 vals['team_id'] = team_id;
	    	}
            self.company_id = session.company_id;
            if(self.company_id){
            	vals['company_id'] = self.company_id;
            }
            var date_opt = $('.date-based-filter').val();
            if(date_opt && date_opt != 'custom_range'){
            	vals['date_opt'] = date_opt;
            }
	    	var params = {
        		model: 'helpdesk.ticket',
        		method: 'load_server_data_for_dashboard',
        		args: [vals],
        		context: self.getContext(),
        	}
        	rpc.query(params, {async: false})
            .then(function(result){
            	self.server_response = result;
            	if(result){
            		if(result.journals && result.journals.length){
            			self.journals = result.journals
            		}
            		var boxes = QWeb.render('HelpdeskCountBoxes', {
    	            	'response':result,
    	            	'widget':self,
    	            });
                	$('.activity_count_boxes').html(boxes);
                	var invoice_list_view = QWeb.render('HelpdeskRows', { 
                		'widget':self,
                		'helpdesk_lines': result.records_body || [],
                		'table_title': '# Tickets',
                	});
                	$('.helpdesk-table-container').html(invoice_list_view);
//                	var planned_activity_table = QWeb.render('ActivityRows', {
//                		'activity_lines': result.planned || [],
//                		'table_title': 'Planned Activity',
//                	});
//                	$('.planned-activity-table-container').html(planned_activity_table);
//                	
//                	var overdue_activity_table = QWeb.render('ActivityRows', {
//                		'activity_lines': result.overdue || [],
//                		'table_title': 'OverDue Activity',
//                	});
//                	$('.overdue-activity-table-container').html(overdue_activity_table);
//                	
//                	var all_activity_table = QWeb.render('ActivityRows', {
//                		'activity_lines': result.all_activity || [],
//                		'table_title': 'All Activity',
//                	});
//
//                	$('.all-activity-table-container').html(all_activity_table);
//                	if(result.activity_types && result.activity_types.length){
//                		self.activity_types = result.activity_types
//                	}
            	}
            });
	    },
	    action_navigate_to: function(ev){
	    	var self = this;
	    	var action = $(ev.currentTarget)[0] ? $(ev.currentTarget)[0].id : false;
	    	var domain = false;
	    	if(!action){
	    		return
	    	}
	    	if(action == 'navigate_close_ticket'){
	    		domain = [['id','in',_.pluck(self.server_response.close_ticket, 'id')]];
	    	} else if (action == 'navigate_done_ticket'){
	    		domain = [['id','in',_.pluck(self.server_response.done_ticket, 'id')]];
	    	} else if (action == 'navigate_all_ticket'){
	    		domain = [['id','in',_.pluck(self.server_response.all_ticket, 'id')]];
	    	} else if (action == 'navigate_open_ticket'){
	    		domain = [['id','in',_.pluck(self.server_response.open_tickt, 'id')]];
	    	}
	    	
	    	
//	    	else if (action == 'navigate_today'){
//	    		domain = [['id','in',_.pluck(self.server_response.today, 'id')]];
//	    	} else if (action == 'navigate_overdue'){
//	    		domain = [['id','in',_.pluck(self.server_response.overdue, 'id')]];
//	    	}
	    	self.do_action({
                name: _t('Ticket'),
                type: 'ir.actions.act_window',
                view_mode: 'tree',
                res_model: 'helpdesk.ticket',
                domain: domain ,
                context: {
                    search_default_no_share: true,
                },
                views: [[false, 'list']],
            });
	    },
	    action_change_team_filter: function(ev){
	    	this.load_invoices();
	    },
	    action_change_user_filter: function(ev){
	    	this.load_invoices();
	    },
	    action_change_partner_filter: function(ev){
	    	this.load_invoices();
	    },
	});

	core.action_registry.add('open_helpdesk_dashboard', InvoiceDashboard);
    return InvoiceDashboard
//	return {
//		InvoiceDashboard: InvoiceDashboard,
//	};

});
