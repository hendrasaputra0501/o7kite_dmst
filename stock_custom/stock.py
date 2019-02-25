import math
import re

from openerp import tools, SUPERUSER_ID
from openerp.osv import osv, fields, expression
from openerp.tools.translate import _
from openerp import netsvc
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT

import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_round
from datetime import datetime
import time

class stock_picking(osv.Model):
	_inherit = "stock.picking"
	_columns = {
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			('auxiliary_material','Auxiliary Materials'),
			('tools','Tools and Spares'),
			('waste','Waste or Scrap Materials'),
			('asset','Asset'),
			('others','Others'),
			], 'Product Type'),
		'default_location_id':fields.many2one('stock.location','Set Default Source Location'),
		'default_dest_location_id':fields.many2one('stock.location','Set Default Destination Location'),
		'date_done_2' : fields.date('Date of Delivery', help="Date of Completion", states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
	}

	def onchange_date_done_2(self, cr, uid, uds, date_done_2, context=None):
		res = {'date_done':False}
		if date_done_2:
			res['date_done'] = datetime.strptime(date_done_2,"%Y-%m-%d").strftime("%Y-%m-%d 12:00:00")
		return {'value':res}

	def set_default_location(self, cr, uid, ids, context=None):
		if context is None:
			context={}
		for picking in self.browse(cr, uid, ids, context=context):
			update_vals = {}
			if picking.default_location_id:
				update_vals.update({'location_id':picking.default_location_id.id})
			if picking.default_dest_location_id:
				update_vals.update({'location_dest_id':picking.default_dest_location_id.id})

			if update_vals:
				move_line_ids = [line.id for line in picking.move_lines]
				self.pool.get('stock.move').write(cr, uid, move_line_ids, update_vals, context=context)
		return True
	
	def has_valuation_moves(self, cr, uid, move):
		return self.pool.get('account.move').search(cr, uid, [
			('ref','=', move.picking_id.name),('journal_id','=',9)
			])

	def action_revert_done(self, cr, uid, ids, context=None):
		if not len(ids):
			return False
		account_move_obj = self.pool.get('account.move')
		prod_move_obj = self.pool.get('production.move')
		for picking in self.browse(cr, uid, ids, context):
			for line in picking.move_lines:
				if self.has_valuation_moves(cr, uid, line):
					# raise osv.except_osv(_('Error'),
					#     _('Line %s has valuation moves (%s). Remove them first')
					#     % (line.name, line.picking_id.name))
					move_all_ids = account_move_obj.search(cr, uid, [('ref','=',picking.name),('journal_id','=',9)])
					account_move_obj.button_cancel(cr,uid,move_all_ids)
					account_move_obj.unlink(cr,uid,move_all_ids)
					
				line.write({'state': 'draft'})
				prod_move_ids = prod_move_obj.search(cr, uid, [('move_id','=',line.id)])
				if prod_move_ids:
					prod_move_obj.action_set_draft(cr, uid, prod_move_ids)
					prod_move_obj.unlink(cr, uid, prod_move_ids)
			self.write(cr, uid, [picking.id], {'state': 'draft'})
			if picking.invoice_state == 'invoiced' and not picking.invoice_id:
				self.write(cr, uid, [picking.id], {'invoice_state': '2binvoiced'})
			wf_service = netsvc.LocalService("workflow")
			# Deleting the existing instance of workflow
			wf_service.trg_delete(uid, 'stock.picking', picking.id, cr)
			wf_service.trg_create(uid, 'stock.picking', picking.id, cr)
		for (id,name) in self.name_get(cr, uid, ids):
			message = _("The stock picking '%s' has been set in draft state.") %(name,)
			self.log(cr, uid, id, message)
		return True

	def action_done(self, cr, uid, ids, context=None):
		"""Changes picking state to done.
		
		This method is called at the end of the workflow by the activity "done".
		@return: True
		"""
		
		res = super(stock_picking, self).action_done(cr, uid, ids, context=context)
		for pick in self.browse(cr, uid, ids, context=context):
			if pick.date_done_2:
				date = datetime.strptime(pick.date_done_2,'%Y-%m-%d').strftime('%Y-%m-%d 12:00:00')
				self.write(cr, uid, ids, {'date_done': date})
		return True

class stock_picking_out(osv.osv):
	_inherit = 'stock.picking.out'
	_columns = {
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			('auxiliary_material','Auxiliary Materials'),
			('tools','Tools and Spares'),
			('waste','Waste or Scrap Materials'),
			('asset','Asset'),
			('others','Others'),
			], 'Product Type'),
		'default_location_id':fields.many2one('stock.location','Set Default Source Location'),
		'default_dest_location_id':fields.many2one('stock.location','Set Default Destination Location'),
		'date_done_2' : fields.date('Date of Delivery', help="Date of Completion", states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
	}
	def action_revert_done(self, cr, uid, ids, context=None):
		#override in order to redirect to stock.picking object
		return self.pool.get('stock.picking').action_revert_done(cr, uid, ids, context=context)

class stock_picking_in(osv.osv):
	_inherit = 'stock.picking.in'
	_columns = {
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			('auxiliary_material','Auxiliary Materials'),
			('tools','Tools and Spares'),
			('waste','Waste or Scrap Materials'),
			('asset','Asset'),
			('others','Others'),
			], 'Product Type'),
		'default_location_id':fields.many2one('stock.location','Set Default Source Location'),
		'default_dest_location_id':fields.many2one('stock.location','Set Default Destination Location'),
		'date_done_2' : fields.date('Date of Delivery', help="Date of Completion", states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
	}
	def action_revert_done(self, cr, uid, ids, context=None):
		#override in order to redirect to stock.picking object
		return self.pool.get('stock.picking').action_revert_done(cr, uid, ids, context=context)


class stock_move(osv.Model):
	_inherit = "stock.move"
	_columns = {
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			('auxiliary_material','Auxiliary Materials'),
			('tools','Tools and Spares'),
			('waste','Waste or Scrap Materials'),
			('asset','Asset'),
			('others','Others'),
			], 'Product Type'),
	}

	_defaults = {
		'product_type' : lambda self, cr, uid, context: context.get('product_type',False),
	}

	def _create_production_moves(self, cr, uid, line, context=None):
		if context is None:
			context = {}
		warehouse_obj = self.pool.get('stock.warehouse')
		loc_obj = self.pool.get('stock.location')
		prod_move_obj = self.pool.get('production.move')
		loc_ids2 = loc_obj.search(cr, uid, [('usage','=','inventory'),('scrap_location','=',True)])
		location_scrap_id = loc_ids2 and loc_ids2[0] or False
		date_done = line.picking_id and line.picking_id.date_done!=False and \
			datetime.strptime(line.picking_id.date_done, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%Y-%m-%d') or \
			(line.date!=False and datetime.strptime(line.date, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%Y-%m-%d') or time.strftime('%Y-%m-%d'))
		prod_move_created_ids = []
		if line.product_id.product_type=='finish_good':
			if line.location_id.usage=='production' and line.location_dest_id.usage=='internal':
				for component in line.product_id.blend_id.blend_component_ids:
					waste_qty = ((line.product_qty*(component.gross_consume_percentage/100.0))/((100.0-component.waste_percentage)/100.0))*(component.waste_percentage/100.0)
					issued_qty = line.product_qty
					new_id1 = prod_move_obj.create(cr, uid, {
						'product_uom' : line.product_uom.id,
						'date_done' : date_done,
						'product_qty' : line.product_qty or 0.0,
						'name' : component.raw_material_categ_id.name or 'Raw Material Consumed',
						# 'blend_id' : line.blend_id.id or False,
						'raw_material_categ_id' : component.raw_material_categ_id.id,
						'location_id' : line.location_id.id,
						'location_dest_id' : line.location_dest_id.id,
						'state': 'draft',
						'move_id':line.id,
					})
					new_id2 = prod_move_obj.create(cr, uid, {
						'date_done' : date_done,
						'product_uom' : line.product_uom.id,
						'product_qty' : waste_qty or 0.0,
						'name' : component.raw_material_categ_id.name or 'Raw Material Wasted',
						'raw_material_categ_id' : component.raw_material_categ_id.id,
						'location_id' : line.location_id.id,
						'location_dest_id' : location_scrap_id,
						'state': 'draft',
						'move_id':line.id,
					})
					prod_move_created_ids.extend([new_id1,new_id2])
		elif line.product_id.product_type=='raw_material':
			if line.location_id.usage=='internal' and line.location_dest_id.usage=='production':
				new_id = prod_move_obj.create(cr, uid, {
					'product_uom' : line.product_uom.id,
					'date_done' : date_done,
					'product_qty' : line.product_qty or 0.0,
					'name' : line.product_id.raw_material_categ_id.name or 'Raw Material Issued',
					# 'blend_id' : line.blend_id.id or False,
					'raw_material_categ_id' : line.product_id.raw_material_categ_id.id,
					'location_id' : line.location_id.id,
					'location_dest_id' : line.location_dest_id.id,
					'state': 'draft',
					'move_id':line.id,
				})
				prod_move_created_ids.append(new_id)

		if prod_move_created_ids:
			prod_move_obj.action_done(cr, uid, prod_move_created_ids)

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		res = super(stock_move, self).action_done(cr, uid, ids, context=context)
		for move in self.browse(cr, uid, ids, context=context):
			if move.product_id.product_type in ('finish_good','raw_material'):
				self._create_production_moves(cr, uid, move, context=context)

			if move.picking_id:
				print "::::::::::::::::::::", move.picking_id.date_done
				self.write(cr, uid, move.id, {'date':move.picking_id.date_done})
			elif context.get('date_done',False):
				self.write(cr, uid, move.id, {'date':context.get('date_done',time.strftime('%Y-%m-%d 12:00:00'))})
		return res

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		prod_move_obj = self.pool.get('production.move')
		res = super(stock_move, self).action_cancel(cr, uid, ids, context=context)
		for move in self.browse(cr, uid, ids, context=context):
			if move.product_id.product_type in ('finish_good','raw_material'):
				prod_move_ids = prod_move_obj.search(cr, uid, [('move_id','=',move.id)])
				if prod_move_ids:
					# for prod_move in prod_move_ids:
					prod_move_obj.action_set_draft(cr, uid, prod_move_ids)
					prod_move_obj.unlink(cr, uid, prod_move_ids)
		return res

class stock_inventory(osv.Model):
	_inherit = "stock.inventory"
	def action_done(self, cr, uid, ids, context=None):
		""" Finish the inventory
		@return: True
		"""
		if context is None:
			context = {}
		move_obj = self.pool.get('stock.move')
		for inv in self.browse(cr, uid, ids, context=context):
			date = inv.date
			context.update({'date_done':date})
			move_obj.action_done(cr, uid, [x.id for x in inv.move_ids], context=context)
			self.write(cr, uid, [inv.id], {'state':'done', 'date_done': date}, context=context)
		return True

	def action_cancel_draft(self, cr, uid, ids, context=None):
		""" Cancels the stock move and change inventory state to draft.
		@return: True
		"""
		for inv in self.browse(cr, uid, ids, context=context):
			self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
			for move in inv.move_ids:
				self.pool.get('stock.move').write(cr, uid, move.id, {'state':'draft'})
				self.pool.get('stock.move').unlink(cr, uid, [move.id])
			self.write(cr, uid, [inv.id], {'state':'draft'}, context=context)
		return True

	def action_cancel_inventory(self, cr, uid, ids, context=None):
		""" Cancels both stock move and inventory
		@return: True
		"""
		move_obj = self.pool.get('stock.move')
		account_move_obj = self.pool.get('account.move')
		for inv in self.browse(cr, uid, ids, context=context):
			move_obj.action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
			for move in inv.move_ids:
				account_move_ids = account_move_obj.search(cr, uid, [('name', '=', move.name)])
				if account_move_ids:
					account_move_data_l = account_move_obj.read(cr, uid, account_move_ids, ['state'], context=context)
					for account_move in account_move_data_l:
						if account_move['state'] == 'posted':
							raise osv.except_osv(_('User Error!'),
												  _('In order to cancel this inventory, you must first unpost related journal entries.'))
						account_move_obj.unlink(cr, uid, [account_move['id']], context=context)
				move_obj.write(cr, uid, move.id, {'state':'draft'})
				move_obj.unlink(cr, uid, [move.id])
			self.write(cr, uid, [inv.id], {'state': 'cancel'}, context=context)
		return True

class stock_picking_custom(osv.Model):
	_name = "stock.picking.custom"
	_columns = {
		'name' : fields.char('Reference', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'create_date' : fields.date('Creation Date', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'date_done' : fields.date('Date Released', readonly=True, states={'draft':[('readonly',False)]}),
		'state' : fields.selection([
			('draft','Draft'),
			('cancel','Cancelled'),
			('done','Transfered'),], 'Status'),
		'move_lines' : fields.one2many('stock.move.custom', 'picking_id', 'Move Lines', readonly=True, states={'draft':[('readonly',False)]}, ondelete='cascade'),
		'shipment_type' : fields.selection([
			('in','Receiving Products'),
			('out','Sending Products'),
			('internal','Internal Transfer'),], 'Shipment Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			], 'Product Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
	}
	_defaults = {
		'name' : lambda *n : '/',
		'state' : lambda *s : 'draft',
		'create_date' : lambda *t : time.strftime('%Y-%m-%d'),
		'shipment_type' : lambda self, cr, uid, context : context.get('shipment_type','internal'),
		'product_type' : lambda self, cr, uid, context : context.get('product_type',False),
	}

	def action_done(self, cr, uid, ids, context=None):
		"""Changes picking state to done.
		
		This method is called at the end of the workflow by the activity "done".
		@return: True
		"""
		if context is None:
			context = {}
		self.action_move(cr, uid, ids, context=context)
		self.write(cr, uid, ids, {'state': 'done'})
		return True

	def action_move(self, cr, uid, ids, context=None):
		"""Process the Stock Moves of the Picking
		
		This method is called by the workflow by the activity "move".
		Normally that happens when the signal button_done is received (button 
		"Done" pressed on a Picking view). 
		@return: True
		"""
		if context is None:
			context = {}
		for pick in self.browse(cr, uid, ids, context=context):
			todo = []
			for move in pick.move_lines:
				# if move.state == 'draft':
				# 	self.pool.get('stock.move').action_confirm(cr, uid, [move.id],
				# 		context=context)
				# 	todo.append(move.id)
				# elif move.state in ('assigned','confirmed'):
				todo.append(move.id)
			if len(todo):
				self.pool.get('stock.move.custom').action_done(cr, uid, todo, context=context)
		self.write(cr, uid, ids, {'state': 'cancel'})
		return True

	def action_set_draft(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		for pick in self.browse(cr, uid, ids, context=context):
			todo = []
			for move in pick.move_lines:
				# if move.state == 'draft':
				# 	self.pool.get('stock.move').action_confirm(cr, uid, [move.id],
				# 		context=context)
				# 	todo.append(move.id)
				# elif move.state in ('assigned','confirmed'):
				todo.append(move.id)
			if len(todo):
				self.pool.get('stock.move.custom').action_set_draft(cr, uid, todo, context=context)
		self.write(cr, uid, ids, {'state': 'draft'}, context=context)
		return True

	def action_cancel(self, cr, uid, ids, context=None):
		"""Cancel the Stock Moves of the Picking
		
		This method is called by the workflow by the activity "move".
		Normally that happens when the signal button_done is received (button 
		"Done" pressed on a Picking view). 
		@return: True
		"""
		if context is None:
			context = {}
		for pick in self.browse(cr, uid, ids, context=context):
			todo = []
			for move in pick.move_lines:
				# if move.state == 'draft':
				# 	self.pool.get('stock.move').action_confirm(cr, uid, [move.id],
				# 		context=context)
				# 	todo.append(move.id)
				# elif move.state in ('assigned','confirmed'):
				todo.append(move.id)
			self.write(cr, uid, pick.id, {'state': 'cancel'}, context=context)
			if len(todo):
				self.pool.get('stock.move.custom').action_cancel(cr, uid, todo, context=context)
		return True


class stock_move_custom(osv.Model):
	def _get_location(self, cr, uid, shipment_type='internal', location_type=None):
		loc_obj = self.pool.get('stock.location')
		warehouse_obj = self.pool.get('stock.warehouse')
		location_id = False
		if location_type is None:
			return False
		if shipment_type=='in' and location_type=='source':
			loc_ids = loc_obj.search(cr, uid, [('usage','=','supplier')])
			location_id = loc_ids and loc_ids[0] or False
		elif shipment_type=='out' and location_type=='destination':
			loc_ids = loc_obj.search(cr, uid, [('usage','=','customer')])
			location_id = loc_ids and loc_ids[0] or False
		else:
			lot_ids = warehouse_obj.search(cr, uid, [])
			if lot_ids:
				loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
			else:
				loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
			location_id = loc_ids and loc_ids[0] or False
			
		return location_id

	def _get_location_id(self, cr, uid, context=None):
		if context is None:
			context = {}
		location_id = False
		if context.get('shipment_type',False):
			location_id = self._get_location(cr, uid, shipment_type=context['shipment_type'], location_type='source')

		return location_id

	def _get_location_dest_id(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		location_id = False
		if context.get('shipment_type',False):
			location_id = self._get_location(cr, uid, shipment_type=context['shipment_type'], location_type='destination')

		return location_id

	_name = "stock.move.custom"
	_columns = {
		'picking_id' : fields.many2one('stock.picking.custom','Reference', readonly=True, states={'draft':[('readonly',False)]}, ondelete='cascade'),
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			], 'Product Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'blend_id' : fields.many2one('product.blend', 'Blend', readonly=True, states={'draft':[('readonly',False)]}),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category', readonly=True, states={'draft':[('readonly',False)]}),
		'name' : fields.char('Description', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'date_done' : fields.date('Date Released', readonly=True, states={'draft':[('readonly',False)]}),
		'state' : fields.selection([
			('draft','Draft'),
			('done','Transfered'),
			('cancel','Cancelled'),], 'Status'),
		'location_id' : fields.many2one('stock.location','Source Location', required=True, domain=[('usage','!=','view')], readonly=True, states={'draft':[('readonly',False)]}),
		'location_dest_id' : fields.many2one('stock.location','Destination Location', required=True, domain=[('usage','!=','view')], readonly=True, states={'draft':[('readonly',False)]}),
		'shipment_type' : fields.selection([
			('in','Receiving Products'),
			('out','Sending Products'),
			('internal','Internal Transfer'),], 'Shipment Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'product_qty' : fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'production_ids' : fields.many2many('stock.production.summary', 'stock_prod_move_rel', 'move_id', 'production_id', 'Production Summary', readonly=True, ondelete='cascade'),
	}

	def onchange_product_id(self, cr, uid, ids, product_type, blend_id, raw_material_categ_id, context=None):
		if context is None:
			context = {}

		blend_obj = self.pool.get('product.blend')
		rm_categ_obj = self.pool.get('product.rm.category')
		res = {}
		if not product_type:
			res.update({'blend_id':False, 'raw_material_categ_id':False, 'product_uom':False})
			return {'value':res}

		if product_type=='finish_good':
			if not blend_id:
				res.update({'product_uom':False})
			else:
				product = blend_obj.browse(cr, uid, blend_id)
				res.update({'product_uom':product.product_uom.id, 'name':product.name, 'raw_material_categ_id':False})
		else:
			if not raw_material_categ_id:
				res.update({'product_uom':False})
			else:
				product = rm_categ_obj.browse(cr, uid, raw_material_categ_id)
				res.update({'product_uom':product.product_uom.id, 'name':product.name, 'blend_id':False})

		return {'value':res}

	_defaults = {
		'state' : lambda *s : 'draft',
		'product_type' : lambda self, cr, uid, context : context.get('product_type',False),
		'shipment_type' : lambda self, cr, uid, context : context.get('shipment_type','internal'),
		'location_id' : _get_location_id,
		'location_dest_id' : _get_location_dest_id,
	}

	_order = "date_done desc, id asc"

	def action_done(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		self.write(cr, uid, ids, {'state': 'done'}, context=context)
		return True

	def action_cancel(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		for move in self.browse(cr, uid, ids, context=context):
			if move.picking_id and move.picking_id.state=='done':
				raise osv.except_osv(_('Error'), _('You cannot directly cancel this move. Please cancel the Picking no. %s'%move.picking_id.name))
			if move.production_ids  and move.production_ids[0].state=='done':
				raise osv.except_osv(_('Error'), _('You cannot directly cancel this move. Please cancel the Production Summary no. %s'%move.production_ids[0].name))

		self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
		return True

	def action_set_draft(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		self.write(cr, uid, ids, {'state': 'draft'}, context=context)
		return True


class production_move(osv.Model):
	_name = "production.move"
	_columns = {
		'name' : fields.char('Description', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'move_id' : fields.many2one("stock.move","Move ID", readonly=True, states={'draft':[('readonly',False)]}, ondelete='cascade'),
		# 'product_type' : fields.selection([
		# 	('finish_good','Finish Goods'),
		# 	('raw_material','Raw Materials'),
		# 	], 'Product Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'date_done'	: fields.date("Date", required=True, readonly=True, states={'draft':[('readonly',False)]}),
		# 'blend_id' : fields.many2one('product.blend', 'Blend', readonly=True, states={'draft':[('readonly',False)]}),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category', readonly=True, states={'draft':[('readonly',False)]}),
		'product_uom' : fields.many2one("product.uom", "Unit of Measure", required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'product_qty' : fields.float("Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'location_id' : fields.many2one("stock.location","Source Location",required=True, domain="[('usage','!=','view')]", readonly=True, states={'draft':[('readonly',False)]}),
		'location_dest_id' : fields.many2one("stock.location","Destination Location",required=True, domain="[('usage','!=','view')]", readonly=True, states={'draft':[('readonly',False)]}),
		'state'	: fields.selection([('draft','Draft'),('done','Done')], "Status", required=True),
	}

	_defaults = {
		'state' : lambda *s : 'draft',
		# 'product_type' : lambda self, cr, uid, context : context.get('product_type',False),
	}

	_order = "date_done desc, id asc"

	def onchange_product_id(self, cr, uid, ids, raw_material_categ_id, context=None):
		if context is None:
			context = {}

		blend_obj = self.pool.get('product.blend')
		rm_categ_obj = self.pool.get('product.rm.category')
		res = {}
		if not raw_material_categ_id:
			res.update({'product_uom':False})
		else:
			product = rm_categ_obj.browse(cr, uid, raw_material_categ_id)
			res.update({'product_uom':product.product_uom.id, 'name':product.name})

		return {'value':res}

	def action_done(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		self.write(cr, uid, ids, {'state': 'done'}, context=context)
		return True

	def action_set_draft(self, cr, uid, ids, context=None):
		""" Makes the move done and if all moves are done, it will finish the picking.
		@return:
		"""
		if context is None:
			context = {}

		self.write(cr, uid, ids, {'state': 'draft'}, context=context)
		return True

	def unlink(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		ctx = context.copy()
		for move in self.browse(cr, uid, ids, context=context):
			if move.state != 'draft':
				raise osv.except_osv(_('User Error!'), _('You can only delete draft moves.'))
		return super(production_move, self).unlink(
			cr, uid, ids, context=ctx)


class stock_production_summary(osv.Model):
	_name = "stock.production.summary"
	_columns = {
		'name' : fields.char('Reference', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'create_date' : fields.date('Creation Date', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'start_date' : fields.date('Start Date', readonly=True, states={'draft':[('readonly',False)]}),
		'end_date' : fields.date('End Date', readonly=True, states={'draft':[('readonly',False)]}),
		'state' : fields.selection([
			('draft','Draft'),
			('confirmed','Escalate Product to Produce'),
			('confirmed2','Confirmed'),
			('cancelled','Cancelled'),
			('posted','Posted on Stock'),], 'Status'),
		'move_produce_ids' : fields.one2many('stock.production.move', 'order_id_produce', 'Products to Produce', readonly=True, states={'confirmed':[('readonly',False)]}, ondelete='cascade'),
		'move_consume_ids' : fields.one2many('stock.production.move', 'order_id_consume', 'Products to Consume', readonly=True, ondelete='cascade'),
		'move_lines' : fields.many2many('stock.move.custom', 'stock_prod_move_rel', 'production_id', 'move_id', 'Move Lines', readonly=True, ondelete='cascade'),
	}

	_defaults = {
		'name' : lambda *n : '/',
		'state' : lambda *s : 'draft',
		'create_date' : lambda *t : time.strftime('%Y-%m-%d'),
	}

	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		if vals.get('name','/')=='/':
			vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'stock.production.summary') or '/'
		return super(stock_production_summary, self).create(cr, uid, vals, context=context)

	def action_confirm(self, cr, uid, ids, context=None):
		if context is None:
			context = {}

		move_pool = self.pool.get('stock.move.custom')
		blend_pool = self.pool.get('product.blend')
		product_context = {}
		for data in self.browse(cr, uid, ids, context=context):
			blend_ids = blend_pool.search(cr, uid, [])
			produce_lines = []
			for blend in blend_pool.browse(cr, uid, blend_ids):
				product_context.update(from_date=data.start_date, to_date=data.start_date, location=[],states=['done'],what=['all_in','all_out'])
				previous_qty = blend_pool.get_product_available(cr, uid, [blend.id], context=product_context)[blend.id]

				product_context.update(from_date=data.start_date, to_date=data.end_date, location=[],states=['done'],what=['in','adj_in'])
				incoming_qty = blend_pool.get_product_available(cr, uid, [blend.id], context=product_context)[blend.id]

				product_context.update(from_date=data.start_date, to_date=data.end_date, location=[],states=['done'],what=['out','adj_out'])
				outgoing_qty = blend_pool.get_product_available(cr, uid, [blend.id], context=product_context)[blend.id]

				produce_lines.append({
					'blend_id' : blend.id,
					'product_uom' : blend.product_uom and blend.product_uom.id or False,
					'ratio_produced_qty' : blend.ratio_produced_qty or 0.0,
					'est_production_qty' : 0.0,
					'produced_qty' : 0.0,
					'previous_qty' : previous_qty,
					'incoming_qty' : incoming_qty,
					'outgoing_qty' : outgoing_qty,
					'closing_qty' : previous_qty+incoming_qty-outgoing_qty,
					})
			self.write(cr, uid, [data.id], {
				'move_produce_ids':map(lambda x:(0,0,x),produce_lines),
				'state':'confirmed'
				})
		return True

	def action_confirm2(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		rm_categ_obj = self.pool.get('product.rm.category')
		product_context = {}
		for data in self.browse(cr, uid, ids, context=context):
			consumed_dict = {}
			for move_produce in data.move_produce_ids:
				for consumed_line in move_produce.consumed_products:
					if consumed_line.raw_material_categ_id.id not in consumed_dict:
						product_context.update(from_date=data.start_date, to_date=data.start_date, location=[],states=['done'],what=['all_in','all_out'])
						previous_qty = rm_categ_obj.get_product_available(cr, uid, [consumed_line.raw_material_categ_id.id], context=product_context)[consumed_line.raw_material_categ_id.id]

						product_context.update(from_date=data.start_date, to_date=data.end_date, location=[],states=['done'],what=['in','adj_in'])
						incoming_qty = rm_categ_obj.get_product_available(cr, uid, [consumed_line.raw_material_categ_id.id], context=product_context)[consumed_line.raw_material_categ_id.id]

						product_context.update(from_date=data.start_date, to_date=data.end_date, location=[],states=['done'],what=['out','adj_out'])
						outgoing_qty = rm_categ_obj.get_product_available(cr, uid, [consumed_line.raw_material_categ_id.id], context=product_context)[consumed_line.raw_material_categ_id.id]
						consumed_dict.update({consumed_line.raw_material_categ_id.id:{
							'raw_material_categ_id' : consumed_line.raw_material_categ_id.id,
							'product_uom' : consumed_line.product_uom.id,
							'issued_qty' : 0.0,
							'consumed_qty' : 0.0,
							'waste_qty' : 0.0,
							'previous_qty' : previous_qty,
							'incoming_qty' : incoming_qty,
							'outgoing_qty' : outgoing_qty,
							'closing_qty' : previous_qty+incoming_qty-outgoing_qty,
							}})
					consumed_dict[consumed_line.raw_material_categ_id.id]['issued_qty'] += (consumed_line.issued_qty or 0.0)
					consumed_dict[consumed_line.raw_material_categ_id.id]['consumed_qty'] += (consumed_line.consumed_qty or 0.0)
					consumed_dict[consumed_line.raw_material_categ_id.id]['waste_qty'] += (consumed_line.waste_qty or 0.0)
					consumed_dict[consumed_line.raw_material_categ_id.id]['closing_qty'] -= (consumed_line.issued_qty or 0.0)
			self.write(cr, uid, [data.id], {
				'move_consume_ids':map(lambda x:(0,0,x),[val for val in consumed_dict.values()]),
				'state':'confirmed2'
				})
		return True

	def _prepare_move_custom(self, cr, uid, ids, line, context=None):
		if context is None:
			context = {}
		warehouse_obj = self.pool.get('stock.warehouse')
		loc_obj = self.pool.get('stock.location')
		location_stock = False
		location_production = False
		lot_ids = warehouse_obj.search(cr, uid, [])
		if lot_ids:
			loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
		else:
			loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
		location_stock = loc_ids and loc_ids[0] or False
		loc_ids = loc_obj.search(cr, uid, [('usage','=','production')])
		location_production = loc_ids and loc_ids[0] or False
		
		res = {
				'state' : 'draft',
				'product_type' : context.get('product_type',False),
				'shipment_type' : 'internal',
				'product_uom' : line.product_uom.id,
		
		}
		if context.get('product_type',False)=='finish_good':
			res.update({
				'date_done' : line.order_id_produce.end_date!=False and line.order_id_produce.end_date or time.strftime('%Y-%m-%d'),
				'product_qty' : line.produced_qty or 0.0,
				'name' : line.blend_id.name or 'Finish Good Production',
				'blend_id' : line.blend_id.id or False,
				'raw_material_categ_id' : False,
				'location_id' : location_production,
				'location_dest_id' : location_stock,
			})
		elif context.get('product_type',False)=='raw_material':
			res.update({
				'date_done' : line.order_id_consume.start_date!=False and line.order_id_consume.start_date or time.strftime('%Y-%m-%d'),
				'product_qty' : line.issued_qty or 0.0,
				'name' : line.raw_material_categ_id.name or 'Raw Material Production',
				'blend_id' : False,
				'raw_material_categ_id' : line.raw_material_categ_id.id or False,
				'location_id' : location_stock,
				'location_dest_id' : location_production,
			})

		return res

	def create_production_moves(self, cr, uid, ids, move_id, line, context=None):
		if context is None:
			context = {}
		warehouse_obj = self.pool.get('stock.warehouse')
		loc_obj = self.pool.get('stock.location')
		prod_move_obj = self.pool.get('production.move')
		loc_ids2 = loc_obj.search(cr, uid, [('usage','=','inventory'),('scrap_location','=',True)])
		location_scrap_id = loc_ids2 and loc_ids2[0] or False
		
		if line.product_id.product_type=='finish_good':
			if line.location_id.usage=='production' and line.location_dest_id.usage=='internal':
				for component in line.product_id.blend_id.blend_component_ids:
					waste_qty = ((line.product_qty*(component.gross_consume_percentage/100.0))/((100.0-component.waste_percentage)/100.0))*(component.waste_percentage/100.0)
					issued_qty = line.product_qty
					prod_move_obj.create(cr, uid, {
						'product_uom' : line.product_uom.id,
						'date_done' : line.date!=False and datetime.strptime(line.date, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%Y-%m-%d') or time.strftime('%Y-%m-%d'),
						'product_qty' : line.product_qty or 0.0,
						'name' : component.raw_material_categ_id.name or 'Raw Material Consumed',
						# 'blend_id' : line.blend_id.id or False,
						'raw_material_categ_id' : component.raw_material_categ_id.id,
						'location_id' : line.location_id.id,
						'location_dest_id' : line.location_dest_id.id,
						'state': 'draft',
						'move_id':move_id,
					})
					prod_move_obj.create(cr, uid, {
						'date_done' : line.date!=False and datetime.strptime(line.date, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%Y-%m-%d') or time.strftime('%Y-%m-%d'),
						'product_uom' : line.product_uom.id,
						'product_qty' : waste_qty or 0.0,
						'name' : component.raw_material_categ_id.name or 'Raw Material Wasted',
						'raw_material_categ_id' : component.raw_material_categ_id.id,
						'location_id' : line.location_id.id,
						'location_dest_id' : location_scrap_id,
						'state': 'draft',
						'move_id':move_id,
					})
		elif line.product_id.product_type=='raw_material':
			prod_move_obj.create(cr, uid, {
				'product_uom' : line.product_uom.id,
				'date_done' : line.date!=False and datetime.strptime(line.date, DEFAULT_SERVER_DATETIME_FORMAT).strftime('%Y-%m-%d') or time.strftime('%Y-%m-%d'),
				'product_qty' : line.product_qty or 0.0,
				'name' : line.product_id.raw_material_categ_id.name or 'Raw Material Issued',
				# 'blend_id' : line.blend_id.id or False,
				'raw_material_categ_id' : line.product_id.raw_material_categ_id.id,
				'location_id' : line.location_id.id,
				'location_dest_id' : line.location_dest_id.id,
				'state': 'draft',
				'move_id':move_id,
			})

		return True

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		move_pool = self.pool.get('stock.move.custom')
		prod_pool = self.pool.get('production.move')
		blend_pool = self.pool.get('product.blend')
		for data in self.browse(cr, uid, ids, context=context):
			move_to_do = []
			# prod_to_do = []
			# for move_produce in data.move_produce_ids:
			# 	if move_produce.produced_qty<=0:
			# 		continue
			# 	move_id = move_pool.create(cr, uid, self._prepare_move_custom(cr, uid, ids, move_produce, context={'product_type':'finish_good'}), context=context)
			# 	for x in self._prepare_prod_move(cr, uid, ids, move_id, move_produce, context={'product_type':'finish_good'}):
			# 		prod_id = prod_pool.create(cr, uid, x, context=context)
			# 		prod_to_do.append(prod_id)
			# 	move_to_do.append(move_id)
			# for consumed_line in data.move_consume_ids:
			# 	if consumed_line.issued_qty<=0:
			# 		continue
			# 	move_id = move_pool.create(cr, uid, self._prepare_move_custom(cr, uid, ids, consumed_line, context={'product_type':'raw_material'}), context=context)
			# 	for x in self._prepare_prod_move(cr, uid, ids, move_id, consumed_line, context={'product_type':'raw_material'}):
			# 		prod_id = prod_pool.create(cr, uid, x, context=context)
			# 		prod_to_do.append(prod_id)
			# 	move_to_do.append(move_id)
			# move_pool.action_done(cr, uid, move_to_do, context=context)
			# prod_pool.action_done(cr, uid, prod_to_do, context=context)
			# self.write(cr, uid, [data.id], {
			# 	'move_lines':[(6, 0, move_to_do)],
			# 	})
		self.write(cr, uid, ids, {'state':'posted'})
		return True

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		move_custom_pool = self.pool.get('stock.move.custom')
		line_prod_pool = self.pool.get('stock.production.move')
		for data in self.browse(cr, uid, ids, context=context):
			self.write(cr, uid, data.id, {'state':'cancelled'}, context=context)
			move_custom_pool.action_cancel(cr, uid, [x.id for x in data.move_lines], context=context)
			for move in data.move_lines:
				move_custom_pool.unlink(cr, uid, move.id)
			for produce_line in data.move_produce_ids:
				line_prod_pool.unlink(cr, uid, produce_line.id)
			for consumed_line in data.move_consume_ids:
				line_prod_pool.unlink(cr, uid, consumed_line.id)
		return True

	def action_set_draft(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		
		return self.write(cr, uid, ids, {'state':'draft'})

class stock_production_move(osv.Model):
	_name = "stock.production.move"
	_columns = {
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=True),

		'order_id_produce' : fields.many2one('stock.production.summary','Production Order 1', ondelete='cascade'),
		'blend_id' : fields.many2one('product.blend', 'Blend'),
		'est_production_qty' : fields.float('Qty to Produce', digits_compute= dp.get_precision('Product Unit of Measure')),
		'ratio_produced_qty' : fields.float('Ratio Produced Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'produced_qty' : fields.float('Produced Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'consumed_products' : fields.one2many('stock.production.move.component','line_id','Consumed Products', ondelete='cascade'),
		
		'order_id_consume' : fields.many2one('stock.production.summary','Production Order 2', ondelete='cascade'),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category'),
		'issued_qty' : fields.float('Issued Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'consumed_qty' : fields.float('Consumed Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		
		'waste_qty' : fields.float('Wasted Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'previous_qty' : fields.float('Opening Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'incoming_qty' : fields.float('Incoming Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'outgoing_qty' : fields.float('Outgoing Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
		'closing_qty' : fields.float('Closing Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
	}

	def onchange_est_production_qty(self, cr, uid, ids, blend_id, product_uom, est_production_qty, \
			ratio_produced_qty, previous_qty, incoming_qty, outgoing_qty, context=None):
		blend_pool = self.pool.get('product.blend')

		blend = blend_pool.browse(cr, uid, blend_id)
		produced_qty = round(est_production_qty*ratio_produced_qty,2)
		closing_qty = (previous_qty+produced_qty+incoming_qty-outgoing_qty)
		total_waste_qty = 0.0
		consumed_products = []
		for component in blend.blend_component_ids:
			waste_qty = ((produced_qty*(component.gross_consume_percentage/100.0))/((100.0-component.waste_percentage)/100.0))*(component.waste_percentage/100.0)
			total_waste_qty += waste_qty
			consumed_products.append({
				'raw_material_categ_id' : component.raw_material_categ_id.id,
				'issued_qty' : est_production_qty*(component.gross_consume_percentage/100.0),
				'consumed_qty' : (produced_qty*(component.gross_consume_percentage/100.0))+waste_qty,
				# 'waste_qty' : produced_qty*(component.waste_percentage/100.0),
				'waste_qty' : waste_qty,
				'product_uom' : component.raw_material_categ_id.product_uom.id,
				})
		return {'value':{'closing_qty':closing_qty,'produced_qty':produced_qty, 'waste_qty':total_waste_qty, 'consumed_products':consumed_products}}

class stock_production_move_component(osv.Model):
	_name = "stock.production.move.component"
	_columns = {
		'line_id' : fields.many2one('stock.production.move','Produced Product', ondelete='cascade'),
		'product_uom' : fields.related('line_id', 'product_uom', relation='product.uom', string='Unit of Measure', required=True),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category'),
		'issued_qty' : fields.float('Issued Qty', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
		'consumed_qty' : fields.float('Consumed Qty', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
		'waste_qty' : fields.float('Wasted Qty', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
	}


class stock_inventory_custom(osv.Model):
	_name = "stock.inventory.custom"
	_columns = {
		'name' : fields.char('Inventory Reference', size=125, required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'date' : fields.date('Creation Date', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'product_type' : fields.selection([
			('finish_good','Finish Goods'),
			('raw_material','Raw Materials'),
			], 'Product Type', required=True, readonly=True, states={'draft':[('readonly',False)]}),
		'state' : fields.selection([
			('draft','Draft'),
			('confirm','Confirmed'),
			('done','Done'),
			('cancel','Cancelled')], 'Status'),
		'rm_inventory_line_ids' : fields.one2many('stock.inventory.custom.line', 'rm_inventory_id', 'Inventory Lines', readonly=True, states={'draft':[('readonly',False)]}, ondelete='cascade'),
		'fg_inventory_line_ids' : fields.one2many('stock.inventory.custom.line', 'fg_inventory_id', 'Inventory Lines', readonly=True, states={'draft':[('readonly',False)]}, ondelete='cascade'),
		'move_lines' : fields.many2many('stock.move.custom', 'stock_invt_move_rel', 'inventory_id', 'move_id', 'Move Lines', readonly=True, ondelete='cascade'),
	}
	_defaults = {
		'state' : lambda *a:'draft',
		'product_type' : lambda *p:'finish_good',
		'date' : lambda *d:time.strftime('%Y-%m-%d'),
	}

	def action_confirm(self, cr, uid, ids, context=None):
		""" Confirm the inventory and writes its finished date
		@return: True
		"""
		if context is None:
			context = {}
		# to perform the correct inventory corrections we need analyze stock location by
		# location, never recursively, so we use a special context
		product_context = dict(context, compute_child=False)

		location_obj = self.pool.get('stock.location')
		blend_obj = self.pool.get('product.blend')
		rm_categ_obj = self.pool.get('product.rm.category')
		move_custom_pool = self.pool.get('stock.move.custom')
		for inv in self.browse(cr, uid, ids, context=context):
			move_ids = []
			for line in (inv.product_type=='finish_good' and inv.fg_inventory_line_ids or inv.rm_inventory_line_ids):
				pid = (inv.product_type=='finish_good' and line.blend_id or line.raw_material_categ_id)
				product_context.update(from_date=inv.date, to_date=inv.date, location=[line.location_id.id],states=['done'],what=['all_in','all_out'])
				if inv.product_type=='finish_good':
					amount = blend_obj.get_product_available(cr, uid, [pid.id], context=product_context)[pid.id]
				elif inv.product_type=='raw_material':
					amount = rm_categ_obj.get_product_available(cr, uid, [pid.id], context=product_context)[pid.id]

				change = line.product_qty - amount
				
				inv_loc = location_obj.search(cr, uid, [('usage','=','inventory')])

				if inv_loc and change:
					location_id = inv_loc[0]
					value = {
						'name': _('INV:') + (pid.name or ''),
						'product_type': inv.product_type,
						'blend_id': inv.product_type=='finish_good' and line.blend_id.id or False,
						'raw_material_categ_id' : inv.product_type=='raw_material' and line.raw_material_categ_id.id or False,
						'product_uom': line.product_uom.id,
						'date_done': inv.date,
						'shipment_type': 'internal',
					}

					if change > 0:
						value.update( {
							'product_qty': change,
							'location_id': location_id,
							'location_dest_id': line.location_id.id,
						})
					else:
						value.update( {
							'product_qty': -change,
							'location_id': line.location_id.id,
							'location_dest_id': location_id,
						})
					move_ids.append(move_custom_pool.create(cr, uid, value))
			
			self.write(cr, uid, [inv.id], {'state': 'confirm', 'move_lines': [(6, 0, move_ids)]})
			# self.pool.get('stock.move').action_confirm(cr, uid, move_ids, context=context)
		return True

	def action_done(self, cr, uid, ids, context=None):
		if context is None:
			context = {}

		move_custom_pool = self.pool.get('stock.move.custom')
		for inv in self.browse(cr, uid, ids, context=context):
			move_custom_pool.action_done(cr, uid, [x.id for x in inv.move_lines])
		return self.write(cr, uid, ids, {'state':'done'}, context=context)

	def action_cancel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		move_custom_pool = self.pool.get('stock.move.custom')
		for inv in self.browse(cr, uid, ids, context=context):
			for move in inv.move_lines:
				if move.state=='done':
					move_custom_pool.action_cancel(cr, uid, [move.id])
				move_custom_pool.unlink(cr, uid, move.id)
		return self.write(cr, uid, ids, {'state':'draft'}, context=context)

class stock_inventory_custom_line(osv.Model):
	def _get_location_id(self, cr, uid, context=None):
		if context is None:
			context = {}
		
		loc_obj = self.pool.get('stock.location')
		warehouse_obj = self.pool.get('stock.warehouse')
		
		lot_ids = warehouse_obj.search(cr, uid, [])
		if lot_ids:
			loc_ids=[warehouse_obj.browse(cr, uid, lot_ids)[0].lot_stock_id.id]
		else:
			loc_ids = loc_obj.search(cr, uid, [('usage','=','internal')])
		location_id = loc_ids and loc_ids[0] or False
			
		return location_id

	_name = "stock.inventory.custom.line"
	_columns = {
		'fg_inventory_id' : fields.many2one('stock.inventory.custom','Reference', ondelete='cascade'),
		'rm_inventory_id' : fields.many2one('stock.inventory.custom','Reference', ondelete='cascade'),
		'location_id' : fields.many2one('stock.location', 'Location', required=True, domain=[('usage','=','internal')]),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category'),
		'blend_id' : fields.many2one('product.blend', 'Blend'),
		'product_qty' : fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=True),
	}
	_defaults = {
		'location_id' : _get_location_id,
	}

	def onchange_product_id(self, cr, uid, ids, blend_id, raw_material_categ_id, context=None):
		if context is None:
			context = {}

		blend_obj = self.pool.get('product.blend')
		rm_categ_obj = self.pool.get('product.rm.category')
		res = {}
		if not blend_id and not raw_material_categ_id:
			res.update({'product_uom':False})
		elif blend_id and not raw_material_categ_id:
			product = blend_obj.browse(cr, uid, blend_id)
			res.update({'product_uom':product.product_uom.id})
		elif raw_material_categ_id and not blend_id:
			product = rm_categ_obj.browse(cr, uid, raw_material_categ_id)
			res.update({'product_uom':product.product_uom.id})
		else:
			raise osv.except_osv(_('Error'), _('You cannot input both of Blend and Raw Material Category'))
		return {'value':res}