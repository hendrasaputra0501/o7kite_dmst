import time
from datetime import datetime
import decimal_precision as dp
import tools
import netsvc
from osv import fields, osv
from tools.translate import _
import openerp.exceptions
import logging
_logger = logging.getLogger(__name__)

class beacukai_document(osv.Model):
	def _get_source_partner_id(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		partner_id = False
		if context.get('shipment_type',False) == 'out':
			user_obj = self.pool.get('res.users')
			partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id

		return partner_id

	def _get_source_address(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		address = ""
		if context.get('shipment_type',False) == 'out':
			user_obj = self.pool.get('res.users')
			partner = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id
			if partner.street:
				address += partner.street
			if partner.street2:
				address += ". "+partner.street2

		return address

	def _get_dest_partner_id(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		partner_id = False
		if context.get('shipment_type',False) == 'in':
			user_obj = self.pool.get('res.users')
			partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id

		return partner_id

	def _get_dest_address(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		address = ""
		if context.get('shipment_type',False) == 'in':
			user_obj = self.pool.get('res.users')
			partner = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id
			if partner.street:
				address += partner.street
			if partner.street2:
				address += ". "+partner.street2

		return address

	_name = "beacukai.document"
	_inherit = ["mail.thread"]
	_description = "Beacukai Document"
	_columns = {
		# 'batch_no' : fields.char('Batch No', required=True),
		'shipment_type' : fields.selection([('in','Pemasukan Barang'),('out','Pengeluaran Barang'),],'Shipment Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'document_type' : fields.selection([('20', 'BC 2.0'),('23', 'BC 2.3'),('24', 'BC 2.4'),('25','BC 2.5'),('261','BC 2.61'),('262','BC 2.62'),('27in', 'BC 2.7 Masukan'),('27out', 'BC 2.7 Keluaran'),('30', 'BC 3.0'),('40', 'BC 4.0'),('41','BC 4.1'),], 'Jenis Dokumen', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'registration_no' : fields.char('No. Pengajuan', size=10, required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'registration_date' : fields.date('Tgl. Pengajuan', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'peb_number' : fields.char('No. PEB', size=20, readonly=True, states={'draft':[('readonly',False)]}),
		'peb_date' : fields.date('Tgl. PEB', readonly=True, states={'draft':[('readonly',False)]}),
		'picking_no' : fields.char('Shipment Number', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'picking_date' : fields.date('Shipment Date', readonly=True, states={'draft':[('readonly',False)]}),
		'source_partner_id' : fields.many2one('res.partner','Source Partner', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'source_partner_address' : fields.char('Partner Address', readonly=True, states={'draft':[('readonly',False)]}),
		'dest_partner_id' : fields.many2one('res.partner','Destination Partner', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'dest_partner_address' : fields.char('Partner Address', readonly=True, states={'draft':[('readonly',False)]}),
		'currency_id' : fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'state' : fields.selection([('draft','Draft BC'), ('validated','Valid BC'), ('cancelled','Cancelled')], 'Status'),
		'product_lines' : fields.one2many('beacukai.document.line','doc_id','Product Lines', required=True, readonly=True, states={'draft':[('readonly',False)]}),
	}
	_defaults = {
		'shipment_type' : lambda self, cr, uid, context: context.get('shipment_type',False),
		'document_type' : lambda self, cr, uid, context: context.get('document_type',False),
		'state' : lambda *s : 'draft',
		'currency_id' : lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id,
		'source_partner_id' : _get_source_partner_id,
		'source_partner_address' : _get_source_address,
		'dest_partner_id' : _get_dest_partner_id,
		'dest_partner_address' : _get_dest_address,
	}

	_order = "registration_date desc, id desc"

	def name_get(self, cr, uid, ids, context=None):
		res = []
		for doc in self.browse(cr, uid, ids, context=context):
			doc_type = dict(self._columns['document_type'].selection).get(doc.document_type)
			name = doc.registration_no!='<Empty>' and doc.registration_no or 'New BC'
			res.append((doc.id, "%s %s"%(doc_type,name)))
		return res

	def onchange_partner_id(self, cr, uid, ids, shipment_type, source_partner_id, dest_partner_id, context=None):
		if context is None:
			context = {}
		partner_obj = self.pool.get('res.partner')
		res = {}
		address = ""
		if shipment_type == 'out':
			if dest_partner_id:
				partner = partner_obj.browse(cr, uid, dest_partner_id, context=context)
				if partner.street:
					address += partner.street
				if partner.street2:
					address += ". "+partner.street2
				res.update({'dest_partner_address':address})
				if partner.default_currency_id:
					res.update({'currency_id':partner.default_currency_id.id})
			else:
				res.update({'dest_partner_address':''})
		elif shipment_type == 'in':
			if source_partner_id:
				partner = partner_obj.browse(cr, uid, source_partner_id, context=context)
				if partner.street:
					address += partner.street
				if partner.street2:
					address += ". "+partner.street2
				res.update({'source_partner_address':address})
				if partner.default_currency_id:
					res.update({'currency_id':partner.default_currency_id.id})
			else:
				res.update({'dest_partner_address':''})

		return {'value':res}

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		for doc in self.browse(cr, uid, ids, context=context):
			self.pool.get('beacukai.document.line').action_done(cr, uid, [x.id for x in doc.product_lines], context=context)
		
		return self.write(cr, uid, ids, {'state':'validated'})

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}

		for doc in self.browse(cr, uid, ids, context=context):
			self.pool.get('beacukai.document.line').action_cancel(cr, uid, [x.id for x in doc.product_lines], context=context)
		
		return self.write(cr, uid, ids, {'state':'cancelled'})

	def action_set_draft(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		for doc in self.browse(cr, uid, ids, context=context):
			self.pool.get('beacukai.document.line').action_set_draft(cr, uid, [x.id for x in doc.product_lines], context=context)

		return self.write(cr, uid, ids, {'state':'draft'})

	def unlink(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		docs = self.read(cr, uid, ids, ['state'], context=context)
		unlink_ids = []

		for t in docs:
			if t['state'] not in ('draft', 'cancelled'):
				raise openerp.exceptions.Warning(_('You cannot delete a BC which is not draft or cancelled. You should cancel it instead.'))
			else:
				unlink_ids.append(t['id'])

		osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
		return True

	def copy(self, cr, uid, id, default=None, context=None):
		default = default or {}
		default.update({
			'state':'draft',
			'picking_date':False,
		})
		if 'registration_no' not in default:
			default.update({
				'picking_no':'<Empty>',
			})
		if 'registration_no' not in default:
			default.update({
				'registration_no':'<Empty>'
			})
		if 'registration_date' not in default:
			default.update({
				'date_due':time.strftime('%Y-%m-%d')
			})
		return super(beacukai_document, self).copy(cr, uid, id, default, context)

class beacukai_document_line(osv.Model):
	def _amount_line(self, cr, uid, ids, prop, unknow_none, unknow_dict):
		res = {}
		tax_obj = self.pool.get('account.tax')
		cur_obj = self.pool.get('res.currency')
		for line in self.browse(cr, uid, ids):
			price = line.price_unit
			taxes = tax_obj.compute_all(cr, uid, line.line_tax_ids, price, line.product_qty, product=line.product_id)
			res[line.id] = taxes['total_included']
			if line.doc_id:
				cur = line.doc_id.currency_id
				res[line.id] = cur_obj.round(cr, uid, cur, res[line.id])
		return res
	
	_name = "beacukai.document.line"
	_log_create = False
	_description = "BC Lines"
	_columns = {
		'doc_id' : fields.many2one('beacukai.document','Reference Doc'),
		'name' : fields.text('Description'),
		'product_id' : fields.many2one('product.product', 'Product', required=True),
		'product_qty' : fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=True),
		'price_unit' : fields.float('Price Unit', digits_compute= dp.get_precision('Account'), required=True),
		'line_tax_ids' : fields.many2many('account.tax', 'beacukai_line_tax_rel', 'line_id', 'tax_id', 'Taxes'),
		# 'price_subtotal' : fields.function(_amount_line, string='Amount', type="float", digits_compute= dp.get_precision('Account'), 
		# 	store={
		# 		'beacukai.document.line' : (lambda self, cr, uid, ids, c={}: ids, ['price_unit','line_tax_ids','product_qty','invoice_id'], 10),
		# 	}),
		'price_subtotal' : fields.float('Amount', digits_compute= dp.get_precision('Account'), required=True), 
		'shipment_type' : fields.related('doc_id', 'shipment_type', type='selection', string='Shipment Type', selection=[('in','Pemasukan Barang'),('out','Pengeluaran Barang'),]),
		'document_type' : fields.related('doc_id', 'document_type', type='selection', string='Jenis Dokumen', selection=[('23', 'BC 2.3'),('25','BC 2.5'),('261','BC 2.61'),('262','BC 2.62'),('27in', 'BC 2.7 Masukan'),('27out', 'BC 2.7 Keluaran'),('30', 'BC 3.0'),('40', 'BC 4.0'),('41','BC 4.1'),]),
		'registration_no' : fields.related('doc_id', 'registration_no', type='char', size=10, string='No. Pengajuan'),
		'registration_date' : fields.related('doc_id', 'registration_date', type='date', string='Tgl. Pengajuan'),
		'picking_no' : fields.related('doc_id', 'picking_no', type='char', sting='Shipment Number'),
		'picking_date' : fields.related('doc_id', 'picking_date', type='date', string='Shipment Date'),
		'currency_id' : fields.related('doc_id', 'currency_id', type='many2one', relation='res.currency', string='Currency'),
		'source_partner_id' : fields.related('doc_id', 'source_partner_id', type='many2one', relation='res.partner', string='Source Partner'),
		'dest_partner_id' : fields.related('doc_id', 'dest_partner_id', type='many2one', relation='res.partner', string='Destination Partner'),
		'state' : fields.selection([('draft','Draft BC'), ('validated','Valid BC'), ('cancelled','Cancelled')], 'Status'),
	}
	_order = "id desc"

	def name_get(self, cr, uid, ids, context=None):
		res = []
		for line in self.browse(cr, uid, ids, context=context):
			doc_type = line.doc_id and dict(self._columns['document_type'].selection).get(line.doc_id.document_type) or ""
			registration_no = line.doc_id and line.doc_id.registration_no or ""
			name = line.name
			res.append((line.id, line.doc_id and "(%s %s) %s"%(doc_type,registration_no,name) or name))
		return res

	def onchange_product_id(self, cr, uid, ids, product_id, context=None):
		if context is None:
			context = {}

		product_obj = self.pool.get('product.product')
		res = {}

		if product_id:
			product = product_obj.browse(cr, uid, product_id)
			res.update({'product_uom':product.uom_id.id, 'name':product.name})
		else:
			res.update({'product_uom':False})

		return {'value':res}

	def onchange_price_unit(self, cr, uid, ids, product_id, price_unit, product_qty, line_tax_ids, context=None):
		res = {}
		warning = {}
		tax_obj = self.pool.get('account.tax')
		cur_obj = self.pool.get('res.currency')
		
		if not product_id:
			warning = {
				'title' : _("Warning!"),
				'message' : _("Please define the product first.")
			}
			return {'value': {'price_unit':0.0, 'product_qty': 0.0, 'price_subtotal': 0.0},'warning': warning}
		if not product_qty or not price_unit:
			warning = {
				'title' : _("Warning!"),
				'message' : _("Please define the product qty or the price unit.")
			}
			return {'value': {'price_unit':0.0, 'product_qty': 0.0, 'price_subtotal': 0.0},'warning': warning}

		product = self.pool.get('product.product').browse(cr, uid, product_id)
		if line_tax_ids and line_tax_ids[0][2]:
			line_tax_ids = tax_obj.browse(cr, uid, line_tax_ids[0][2])
		else:
			line_tax_ids = []
		taxes = tax_obj.compute_all(cr, uid, line_tax_ids, price_unit, product_qty, product=product)
		res['price_subtotal'] = taxes['total_included']
		return {'value':res}

	def onchange_price_subtotal(self, cr, uid, ids, product_id, amount, product_qty, line_tax_ids, context=None):
		res = {}
		warning = {}
		tax_obj = self.pool.get('account.tax')
		cur_obj = self.pool.get('res.currency')
		
		if not product_id:
			warning = {
				'title' : _("Warning!"),
				'message' : _("Please define the product first.")
			}
			return {'value': {'price_unit':0.0, 'product_qty': 0.0, 'price_subtotal': 0.0},'warning': warning}
		if not product_qty and not amount:
			warning = {
				'title' : _("Warning!"),
				'message' : _("Please define the product qty or the price unit.")
			}
			return {'value': {'price_unit':0.0, 'product_qty': 0.0, 'price_subtotal': 0.0},'warning': warning}

		product = self.pool.get('product.product').browse(cr, uid, product_id)
		if line_tax_ids and line_tax_ids[0][2]:
			line_tax_ids = tax_obj.browse(cr, uid, line_tax_ids[0][2])
		else:
			line_tax_ids = []
		# taxes = tax_obj.compute_all(cr, uid, line_tax_ids, price_unit, product_qty, product=product)
		price_unit = amount
		total_percent =	sum([(1+tax.amount) for tax in line_tax_ids if tax.type=='percent'])
		total_fixed = sum([tax.amount for tax in line_tax_ids if tax.type=='fixed'])
		amount -= total_fixed
		if total_percent:
			price_unit = amount/total_percent
		if not product_qty:
			return {'value':res} 
		res['price_unit'] = price_unit/product_qty
		return {'value':res}

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		
		return self.write(cr, uid, ids, {'state':'validated'})

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		
		return self.write(cr, uid, ids, {'state':'cancelled'})

	def action_set_draft(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		
		return self.write(cr, uid, ids, {'state':'draft'})

	# def unlink(self, cr, uid, ids, context=None):
	# 	if context is None:
	# 		context = {}
	# 	lines = self.read(cr, uid, ids, ['state','doc_id'], context=context)
	# 	unlink_ids = []

	# 	for t in lines:
	# 		if t['state'] not in ('draft', 'cancelled'):
	# 			raise openerp.exceptions.Warning(_('[%s]. You cannot delete a BC which is not draft or cancelled. You should cancel it instead.'%(t['states'])))
	# 		else:
	# 			unlink_ids.append(t['id'])

	# 	osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
	# 	return True


class beacukai_document_line_in(osv.osv):
	_name = "beacukai.document.line.in"
	_inherit = "beacukai.document.line"
	_table = "beacukai_document_line"
	_description = "Incoming BC lines"

	def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
		return self.pool.get('beacukai.document.line').search(cr, user, args, offset, limit, order, context, count)

	def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
		return self.pool.get('beacukai.document.line').read(cr, uid, ids, fields=fields, context=context, load=load)

	def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
		return self.pool['beacukai.document.line'].read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)

	def check_access_rights(self, cr, uid, operation, raise_exception=True):
		#override in order to redirect the check of acces rights on the stock.picking object
		return self.pool.get('beacukai.document.line').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

	def check_access_rule(self, cr, uid, ids, operation, context=None):
		#override in order to redirect the check of acces rules on the stock.picking object
		return self.pool.get('sbeacukai.document.line').check_access_rule(cr, uid, ids, operation, context=context)

	def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
		#override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
		#instead of it's own workflow (which is not existing)
		return self.pool.get('beacukai.document.line')._workflow_trigger(cr, uid, ids, trigger, context=context)

	def _workflow_signal(self, cr, uid, ids, signal, context=None):
		#override in order to fire the workflow signal on given stock.picking workflow instance
		#instead of it's own workflow (which is not existing)
		return self.pool.get('beacukai.document.line')._workflow_signal(cr, uid, ids, signal, context=context)

	def message_post(self, *args, **kwargs):
		"""Post the message on stock.picking to be able to see it in the form view when using the chatter"""
		return self.pool.get('beacukai.document.line').message_post(*args, **kwargs)

	def message_subscribe(self, *args, **kwargs):
		"""Send the subscribe action on stock.picking model as it uses _name in request"""
		return self.pool.get('beacukai.document.line').message_subscribe(*args, **kwargs)

	def message_unsubscribe(self, *args, **kwargs):
		"""Send the unsubscribe action on stock.picking model to match with subscribe"""
		return self.pool.get('beacukai.document.line').message_unsubscribe(*args, **kwargs)

	def default_get(self, cr, uid, fields_list, context=None):
		# merge defaults from stock.picking with possible defaults defined on stock.picking.in
		defaults = self.pool['beacukai.document.line'].default_get(cr, uid, fields_list, context=context)
		in_defaults = super(beacukai_document_line_in, self).default_get(cr, uid, fields_list, context=context)
		defaults.update(in_defaults)
		return defaults

	_columns = {
	}

class beacukai_document_line_out(osv.osv):
	_name = "beacukai.document.line.out"
	_inherit = "beacukai.document.line"
	_table = "beacukai_document_line"
	_description = "Outgoing BC lines"

	def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
		return self.pool.get('beacukai.document.line').search(cr, user, args, offset, limit, order, context, count)

	def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
		return self.pool.get('beacukai.document.line').read(cr, uid, ids, fields=fields, context=context, load=load)

	def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
		return self.pool['beacukai.document.line'].read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)

	def check_access_rights(self, cr, uid, operation, raise_exception=True):
		#override in order to redirect the check of acces rights on the stock.picking object
		return self.pool.get('beacukai.document.line').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

	def check_access_rule(self, cr, uid, ids, operation, context=None):
		#override in order to redirect the check of acces rules on the stock.picking object
		return self.pool.get('sbeacukai.document.line').check_access_rule(cr, uid, ids, operation, context=context)

	def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
		#override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
		#instead of it's own workflow (which is not existing)
		return self.pool.get('beacukai.document.line')._workflow_trigger(cr, uid, ids, trigger, context=context)

	def _workflow_signal(self, cr, uid, ids, signal, context=None):
		#override in order to fire the workflow signal on given stock.picking workflow instance
		#instead of it's own workflow (which is not existing)
		return self.pool.get('beacukai.document.line')._workflow_signal(cr, uid, ids, signal, context=context)

	def message_post(self, *args, **kwargs):
		"""Post the message on stock.picking to be able to see it in the form view when using the chatter"""
		return self.pool.get('beacukai.document.line').message_post(*args, **kwargs)

	def message_subscribe(self, *args, **kwargs):
		"""Send the subscribe action on stock.picking model as it uses _name in request"""
		return self.pool.get('beacukai.document.line').message_subscribe(*args, **kwargs)

	def message_unsubscribe(self, *args, **kwargs):
		"""Send the unsubscribe action on stock.picking model to match with subscribe"""
		return self.pool.get('beacukai.document.line').message_unsubscribe(*args, **kwargs)

	def default_get(self, cr, uid, fields_list, context=None):
		# merge defaults from stock.picking with possible defaults defined on stock.picking.in
		defaults = self.pool['beacukai.document.line'].default_get(cr, uid, fields_list, context=context)
		in_defaults = super(beacukai_document_line_out, self).default_get(cr, uid, fields_list, context=context)
		defaults.update(in_defaults)
		return defaults

	_columns = {
	}