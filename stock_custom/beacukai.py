import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import tools
import netsvc
from osv import fields, osv
from tools.translate import _
from openerp import netsvc
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP

class beacukai_document(osv.Model):
	_inherit = "beacukai.document"
	_columns = {
		'picking_custom_ids' : fields.many2many('stock.picking.custom', 'beacukai_picking_rel', 'doc_id', 'picking_id', 'Pickings Custom'),
		'picking_ids' : fields.many2many('stock.picking', 'beacukai_stock_picking_rel', 'doc_id', 'picking_id', 'Pickings'),
	}

	def _prepare_picking_custom(self, cr, uid, ids, beacukai, context=None):
		if context is None:
			context = {}
		res = {
			'create_date' : time.strftime('%Y-%m-%d'),
			'date_done' : beacukai.picking_date!=False and beacukai.picking_date or time.strftime('%Y-%m-%d'),
			'name' : context.get('default_name',False) and context['default_name'] or beacukai.picking_no or '/',
			'state' : 'draft',
			'shipment_type' : beacukai.shipment_type,
			'product_type' : context.get('product_type',False),
		}
		return res

	def _prepare_picking(self, cr, uid, ids, beacukai, context=None):
		if context is None:
			context = {}
		res = {
			'date' : datetime.strptime(time.strftime('%Y-%m-%d'),DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00'),
			'date_done' : beacukai.picking_date!=False and datetime.strptime(beacukai.picking_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') or \
							(beacukai.registration_date!=False and datetime.strptime(beacukai.registration_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') \
								or time.strftime('%Y-%m-%d 12:00:00')),
			'date_done_2' : beacukai.picking_date!=False and beacukai.picking_date or \
							(beacukai.registration_date!=False and beacukai.registration_date \
								or time.strftime('%Y-%m-%d')),
			'name' : context.get('default_name',False) and context['default_name'] or beacukai.picking_no or '/',
			'state' : 'draft',
			'type' : beacukai.shipment_type,
			'partner_id' : beacukai.shipment_type=='in' and (beacukai.source_partner_id and beacukai.source_partner_id.id or False) or (beacukai.dest_partner_id and beacukai.dest_partner_id.id or False),
			'invoice_state': 'none',
			'company_id': self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
			# 'product_type' : context.get('product_type',False),
		}
		return res

	def _prepare_move_custom(self, cr, uid, ids, line, context=None):
		if context is None:
			context = {}

		warehouse_obj = self.pool.get('stock.warehouse')
		loc_obj = self.pool.get('stock.location')
		location_id = False
		location_dest_id = False
		if line.shipment_type=='in':
			location_id = line.source_partner_id.property_stock_supplier and line.source_partner_id.property_stock_supplier.id or False
			location_dest_id = line.dest_partner_id.property_stock_supplier and line.dest_partner_id.property_stock_customer.id or False
			if not location_id or not location_dest_id:
				loc_ids = loc_obj.search(cr, uid, [('usage','=','supplier')])
				location_id = loc_ids and loc_ids[0] or False
				lot_ids = warehouse_obj.search(cr, uid, [])
				if lot_ids:
					loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
				else:
					loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
				location_dest_id = loc_ids and loc_ids[0] or False
		elif line.shipment_type == 'out':
			location_id = line.source_partner_id.property_stock_supplier and line.source_partner_id.property_stock_customer.id or False
			location_dest_id = line.dest_partner_id.property_stock_supplier and line.dest_partner_id.property_stock_customer.id or False
			if not location_id or not location_dest_id:
				lot_ids = warehouse_obj.search(cr, uid, [])
				if lot_ids:
					loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
				else:
					loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
				location_id = loc_ids and loc_ids[0] or False
				loc_ids = loc_obj.search(cr, uid, [('usage','=','customer')])
				location_dest_id = loc_ids and loc_ids[0] or False
		res = {
			'date_done' : line.doc_id.picking_date!=False and line.doc_id.picking_date or time.strftime('%Y-%m-%d'),
			'name' : line.name or line.product_id.name or '',
			'state' : 'draft',
			'shipment_type' : line.shipment_type,
			'blend_id' : line.product_id.product_type=='finish_good' and line.product_id.blend_id.id or False,
			'raw_material_categ_id' : line.product_id.product_type=='raw_material' and line.product_id.raw_material_categ_id.id or False,
			'product_type' : line.product_id.product_type,
			'product_qty' : line.product_qty,
			'product_uom' : line.product_uom.id,
			'location_id' : location_id,
			'location_dest_id' : location_dest_id,
		}
		return res

	def _prepare_move(self, cr, uid, ids, line, context=None):
		if context is None:
			context = {}

		warehouse_obj = self.pool.get('stock.warehouse')
		loc_obj = self.pool.get('stock.location')
		location_id = False
		location_dest_id = False
		if line.shipment_type=='in':
			location_id = line.source_partner_id.property_stock_supplier and line.source_partner_id.property_stock_supplier.id or False
			location_dest_id = line.dest_partner_id.property_stock_customer and line.dest_partner_id.property_stock_customer.id or False
			if not location_id or not location_dest_id:
				loc_ids = loc_obj.search(cr, uid, [('usage','=','supplier')])
				location_id = loc_ids and loc_ids[0] or False
				lot_ids = warehouse_obj.search(cr, uid, [])
				if lot_ids:
					loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
				else:
					loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
				location_dest_id = loc_ids and loc_ids[0] or False
		elif line.shipment_type == 'out':
			location_id = line.source_partner_id.property_stock_customer and line.source_partner_id.property_stock_customer.id or False
			location_dest_id = line.dest_partner_id.property_stock_customer and line.dest_partner_id.property_stock_customer.id or False
			if not location_id or not location_dest_id:
				lot_ids = warehouse_obj.search(cr, uid, [])
				if lot_ids:
					loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
				else:
					loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
				location_id = loc_ids and loc_ids[0] or False
				loc_ids = loc_obj.search(cr, uid, [('usage','=','customer')])
				location_dest_id = loc_ids and loc_ids[0] or False
		res = {
			'date' : line.doc_id.picking_date!=False and datetime.strptime(line.doc_id.picking_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') or \
						(line.doc_id.registration_date and datetime.strptime(line.doc_id.registration_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') or \
							time.strftime('%Y-%m-%d 12:00:00')),
			'date_expected' : line.doc_id.picking_date!=False and datetime.strptime(line.doc_id.picking_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') or \
						(line.doc_id.registration_date and datetime.strptime(line.doc_id.registration_date, DEFAULT_SERVER_DATE_FORMAT).strftime('%Y-%m-%d 12:00:00') or \
							time.strftime('%Y-%m-%d 12:00:00')),
			'name' : line.name or line.product_id.name or '',
			'state' : 'draft',
			'type' : line.shipment_type,
			'partner_id' : line.shipment_type=='in' and (line.doc_id.source_partner_id and line.doc_id.source_partner_id.id or False) or (line.doc_id.dest_partner_id and line.doc_id.dest_partner_id.id or False),
			'product_id' : line.product_id and line.product_id.id or False,
			'product_qty' : line.product_qty,
			'product_uom' : line.product_uom.id,
			'product_uos_qty' : line.product_qty,
			'product_uos' : line.product_uom.id,
			'location_id' : location_id,
			'location_dest_id' : location_dest_id,
			'company_id': self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
		}
		return res

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}

		picking_custom_pool = self.pool.get('stock.picking.custom')
		picking_pool = self.pool.get('stock.picking')
		wf_service = netsvc.LocalService("workflow")
		for doc in self.browse(cr, uid, ids, context=context):
			picking_custom_ids = []
			picking_ids = []
			product_types = [(x.product_id.product_type and x.product_id.product_type or 'other') for x in doc.product_lines]
			n = 0
			dict_temp = {}
			ctx = context.copy()
				
			pick_dict = self._prepare_picking(cr, uid, ids, doc, context=ctx)
			
			for line in doc.product_lines:
				if not pick_dict.get('move_lines',False):
					pick_dict.update({'move_lines':[]})
				pick_dict['move_lines'].append((0, 0, self._prepare_move(cr, uid, ids, line, context=ctx)))

			pick_id = picking_pool.create(cr, uid, pick_dict, context=context)
			picking_ids.append(pick_id)

			for picking_id in picking_ids:
				wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
				picking_pool.action_move(cr, uid, [picking_id], context=context)
				wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_done', cr)
			self.write(cr, uid, doc.id, {'picking_ids': map(lambda x:(4,x),picking_ids)}, context=ctx)
		return super(beacukai_document, self).action_done(cr, uid, ids, context=context)

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		picking_custom_pool = self.pool.get('stock.picking.custom')
		picking_pool = self.pool.get('stock.picking')
		wf_service = netsvc.LocalService("workflow")
		for doc in self.browse(cr, uid, ids, context=context):
			if doc.picking_ids:
				for picking in doc.picking_ids:
					for line in picking.move_lines:
						line.write({'state': 'draft'})
					picking_pool.write(cr, uid, [picking.id], {'state': 'draft'})
					# Deleting the existing instance of workflow
					wf_service.trg_delete(uid, 'stock.picking', picking.id, cr)
					wf_service.trg_create(uid, 'stock.picking', picking.id, cr)
					picking_pool.unlink(cr, uid, [picking.id], context=context)
			
		return super(beacukai_document, self).action_cancel(cr, uid, ids, context=context)

class beacukai_document_line(osv.Model):
	_inherit = "beacukai.document.line"
	_columns = {
		'move_custom_id' : fields.many2one('stock.move.custom','Move ID'),
	}