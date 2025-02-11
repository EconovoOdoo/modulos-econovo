# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import OrderedDict
from odoo import fields, http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv import expression
import werkzeug
from datetime import datetime, date
from odoo.tools import groupby as groupbyelem
from operator import itemgetter
from odoo.tools import float_compare
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.osv.expression import OR
import base64


class CustomerPortal(CustomerPortal):

#    def _prepare_portal_layout_values(self):
#        values = super(CustomerPortal, self)._prepare_portal_layout_values()
#        warranty_pool = request.env['warranty.warranty']
#        partner_id = request.env.user.partner_id.id
#        warranty_count = warranty_pool.sudo().search_count([
#            ('customer_id', '=',partner_id),('state', '!=','close')
#        ])
#        values.update({
#            'warranty_count': warranty_count,
#        })
#        return values
        
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        warranty_pool = request.env['warranty.warranty']
        partner_id = request.env.user.partner_id.id
        warranty_count = warranty_pool.sudo().search_count([
            ('customer_id', '=',partner_id),('state', '!=','close')
        ])
        values.update({
            'warranty_count': warranty_count,
        })
        return values
    
    
    @http.route(['/my/warranty', '/my/warranty/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_warranty(self, page=1, date_begin=None, date_end=None, sortby=None,filterby=None,groupby='none',search=None,search_in=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        warranty_pool = request.env['warranty.warranty']

        domain = [
            ('customer_id', '=',request.env.user.partner_id.id )
        ]
        
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'date desc'},
			'number': {'label': _('Number'), 'order': 'number desc'},
		
        }
        
        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('All')},
#            'customer_id': {'input': 'customer_id', 'label': _('Customer')},
            'company_id': {'input': 'company_id', 'label': _('Company')},
            'product_id': {'input': 'product_id', 'label': _('Product')},
            
        }
        today = fields.Date.today()
        this_week_end_date = fields.Date.to_string(fields.Date.from_string(today) + timedelta(days=7))
        week_ago = datetime.today() - timedelta(days=7)
        month_ago = (datetime.today() - relativedelta(months=1)).strftime('%Y-%m-%d %H:%M:%S')
        starting_of_year = datetime.now().date().replace(month=1, day=1)    
        ending_of_year = datetime.now().date().replace(month=12, day=31)

        def sd(date):
            return fields.Datetime.to_string(date)
        def previous_week_range(date):
            start_date = date + timedelta(-date.weekday(), weeks=-1)
            end_date = date + timedelta(-date.weekday() - 1)
            return {'start_date':start_date.strftime('%Y-%m-%d %H:%M:%S'), 'end_date':end_date.strftime('%Y-%m-%d %H:%M:%S')}
        
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'today': {'label': _('Today'), 'domain': [('date', '>=', datetime.strftime(date.today(),'%Y-%m-%d 00:00:00')),('date', '<=', datetime.strftime(date.today(),'%Y-%m-%d 23:59:59'))]},
            'yesterday':{'label': _('Yesterday'), 'domain': [('date', '>=', datetime.strftime(date.today() - timedelta(days=1),'%Y-%m-%d 00:00:00')),('date', '<=', datetime.strftime(date.today(),'%Y-%m-%d 23:59:59'))]},
            'week': {'label': _('This Week'),
                     'domain': [('date', '>=', sd(datetime.today() + relativedelta(days=-today.weekday()))), ('date', '<=', this_week_end_date)]},
            'last_seven_days':{'label':_('Last 7 Days'),
                         'domain': [('date', '>=', sd(week_ago)), ('date', '<=', sd(datetime.today()))]},
            'last_week':{'label':_('Last Week'),
                         'domain': [('date', '>=', previous_week_range(datetime.today()).get('start_date')), ('date', '<=', previous_week_range(datetime.today()).get('end_date'))]},
            
            'last_month':{'label':_('Last 30 Days'),
                         'domain': [('date', '>=', month_ago), ('date', '<=', sd(datetime.today()))]},
            'month':{'label': _('This Month'),
                    'domain': [
                       ("date", ">=", sd(today.replace(day=1))),
                       ("date", "<", (today.replace(day=1) + relativedelta(months=1)).strftime('%Y-%m-%d 00:00:00'))
                    ]
                },
            'year':{'label': _('This Year'),
                    'domain': [
                       ("date", ">=", sd(starting_of_year)),
                       ("date", "<=", sd(ending_of_year)),
                    ]
                }
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']     
        
        # default sortby order
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']
        
#        archive_groups = self._get_archive_groups('account.payment')
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        # count for pager
        payment_count = warranty_pool.search_count(domain)


        searchbar_inputs = {
            'number': {'input': 'number', 'label': _('Search in Number')},
			'sale_id': {'input': 'sale_id', 'label': _('Search in Sale Order')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }
        
        if not search_in:
            search_in = 'number'

		# search
        if search and search_in:
        	search_domain = []
        	if search_in in ('number', 'all'):
        		search_domain = OR([search_domain, [('number', 'ilike', search)]])
        	if search_in in ('sale_id', 'all'):
        		search_domain = OR([search_domain, [('sale_id', 'ilike', search)]])
#        	if search_in in ('state', 'all'):
#        		search_domain = OR([search_domain, [('state', 'ilike', search)]])
        	domain += search_domain


        # make pager
        pager = portal_pager(
            url="/my/warranty",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby,'search_in': search_in,'search': search},
            total=payment_count,
            page=page,
            step=self._items_per_page
        )
        # search the count to display, according to the pager data
        warranty = warranty_pool.search(domain, order=sort_order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_payment_history'] = warranty.ids[:100]
        if groupby == 'product_id':
            grouped_warranty = [request.env['warranty.warranty'].concat(*g) for k, g in groupbyelem(warranty, itemgetter('product_id'))]
        elif groupby == 'company_id':
            grouped_warranty = [request.env['warranty.warranty'].concat(*g) for k, g in groupbyelem(warranty, itemgetter('company_id'))]
        else:
            grouped_warranty = [warranty]
        values.update({
            'date': date_begin,
            'warranty': warranty.sudo(),
            'page_name': 'payment',
            'grouped_warranty': grouped_warranty,
            'pager': pager,
#            'archive_groups': archive_groups,
            'default_url': '/my/warranty',
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby':searchbar_groupby,
            'filterby': filterby,
            'sortby': sortby,
            'groupby': groupby,
	    'searchbar_inputs': searchbar_inputs,
	    'search_in': search_in,
	    'search': search,
        })
        return request.render("dev_warranty_management.portal_my_warranty", values)


    @http.route(['/my/warranty/<int:order_id>'], type='http', auth="public", website=True)
    def portal_warranty_page(self, order_id, report_type=None, access_token=None, message=False, download=False, **kw):
        try:
            warranty_sudo = self._document_check_access('warranty.warranty', order_id, access_token=access_token) 
        except (AccessError, MissingError):
            return request.redirect('/my')
        now = fields.Date.today()
        if report_type in ('html', 'pdf', 'text'):
        	return self._show_report(model=warranty_sudo, report_type=report_type, report_ref='dev_warranty_management.action_warranty_card_report', download=download)
        if warranty_sudo and request.session.get('view_payment_%s' % warranty_sudo.id) != now and request.env.user.share and access_token:
            request.session['view_rma_%s' % warranty_sudo.id] = now
            body = _('Leave viewed by customer')
            _message_post_helper(res_model='warranty.warranty', res_id=warranty_sudo.id, message=body, token=warranty_sudo.access_token, message_type='notification', subtype_xmlid="mail.mt_note", partner_ids=warranty_sudo.user_id.sudo().partner_id.ids)
        ticket_type = request.env['helpdesk.ticket.type'].sudo().search([])
        values = {
            'warranty': warranty_sudo,
            'message': message,
            'token': access_token,
            'bootstrap_formatting': True,
            'report_type': 'html',
			'p_name':warranty_sudo.number,
			'ticket_type':ticket_type,
        }
        if warranty_sudo.company_id:
            values['res_company'] = warranty_sudo.company_id
        if warranty_sudo.number:
            history = request.session.get('my_contact_history', [])
        values.update(get_records_pager(history, warranty_sudo))
        return request.render('dev_warranty_management.warranty_portal_template', values)

    @http.route(['/my/waranty/<int:warranty_id>/create_ticket'], type='http', auth="public", methods=['POST'], website=True)
    def portal_warranty_edit(self, warranty_id, access_token=None, **post):
        try:
            warranty = self._document_check_access('warranty.warranty', warranty_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        waranty_obj = request.env['warranty.warranty'].browse(warranty_id)
        vals={
            'name':post.get('claim_subject'),
            'ticket_type_id':post.get('type'),
            'partner_id':waranty_obj.customer_id.id or False,
            'partner_email':post.get('email'),
            'priority':post.get('rate'),
            'warranty_id':warranty_id,
            'sale_id':waranty_obj.sale_id and waranty_obj.sale_id.id or False,
            'waranty_type':waranty_obj.waranty_type,
            'start_date':waranty_obj.start_date,
            'end_date':waranty_obj.end_date,
            'product_id':waranty_obj.product_id and waranty_obj.product_id.id or False,
            'description':post.get('claim_details'),
        }
        ticket_id = request.env['helpdesk.ticket'].sudo().create(vals)
        ticket_id.company_id = ticket_id.env.company
        doc_id = request.env['ir.attachment'].sudo().create({
                        'name': post['attachment_war'].filename,
                        'datas': base64.b64encode(post['attachment_war'].read()),
                        'type': 'binary',
                        'res_model': 'helpdesk.ticket',
                        'res_id': ticket_id.id
                    })
        values = {
            'ticket_number': ticket_id,
        }
        return request.render('dev_warranty_management.warranty_portal_thank_you',values)
        
    @http.route(['/dev_warranty_track'], type='json', methods=['POST'], website=True, auth="public")
    def dev_track_warranty(self, do_no, **kw):
        warranty = request.env['warranty.warranty'].sudo().search([('number','=',do_no)],limit=1)
        status = False
        if warranty:
            if warranty.state == 'draft':
                status = 'Draft'
            elif warranty.state == 'running':
                status = 'Running'
          #  elif warranty.state == 'done':
           #     status = 'Done'
            elif warranty.state == 'invoiced':
                status = 'Invoiced'
            elif warranty.state == 'expire':
                status = 'Expired'
            elif warranty.state == 'cancel':
                status = 'Cancel'
                
            if warranty.start_date:
            	start_date = warranty.start_date.strftime('%d-%m-%Y')
            	
            if warranty.end_date:
            	end_date = warranty.end_date.strftime('%d-%m-%Y')
            	
            partner = warranty.customer_id
                      
            res = {
                'customer':partner.name or '',
                'status':status,
                'start_date':start_date or '',
                'end_date':end_date or '',
                'sale_order':warranty.sale_id.name
            }
            return res
        else:
            return False
    
    @http.route(['/tracking'], type='http', auth="public", website=True)
    def warranty_tracking(self, **post):
        return request.render("dev_warranty_management.warranty_tracking_page")



