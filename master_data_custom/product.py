import math
import re

from openerp import tools, SUPERUSER_ID
from openerp.osv import osv, fields, expression
from openerp.tools.translate import _

import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_round
from datetime import datetime

class product_category(osv.Model):
	_inherit = "product.category"
	_columns = {
		'product_type' : fields.selection([
			('finish_good','Barang Jadi'),
			('raw_material','Bahan Baku'),
			# ('auxiliary_material','Auxiliary Materials'),
			# ('tools','Tools and Spares'),
			('waste','Sampah Produksi'),
			# ('asset','Asset'),
			('others','Others'),
			], 'Product Type'),
	}
	
class product_rm_categ(osv.Model):
	_name = "product.rm.category"
	_columns = {
		'name' : fields.char('Description', required=True),
		'code' : fields.char('Code/Alias', required=True),
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=True),
	}

class product_blend(osv.Model):
	def _compute_consume_percent(self, cr, uid, ids, field_names, arg=None, context=None):
		result = {}
		if not ids: return result
		
		for line in self.browse(cr,uid,ids):
			result[line.id] = line.gross_consume_percentage - (line.gross_consume_percentage * (line.waste_percentage / 100))
		return result

	_name = "product.blend.component"
	_columns = {
		'blend_id' : fields.many2one('product.blend', 'Blend'),
		# 'name' : fields.char('Description', required=True),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category', required=True),
		'gross_consume_percentage' : fields.float('Gross Consume %', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
		'consume_percentage' : fields.function(_compute_consume_percent, type='float', string='Net Consume %', digits_compute= dp.get_precision('Product Unit of Measure'), method=True, 
			store={
				'product.blend.component':(lambda self,cr,uid,ids,context={}:ids,['gross_consume_percentage','waste_percentage'],10),
			}),
		'waste_percentage' : fields.float('Waste %', digits_compute= dp.get_precision('Product Unit of Measure'), required=True),
	}
	_defaults = {
		'waste_percentage' : 0.0,
		'consume_percentage' : 0.0,

	}

class product_blend(osv.Model):
	_name = "product.blend"
	_columns = {
		'code' : fields.char('Code/Alias', required=True),
		'name' : fields.char('Description', required=True),
		'product_uom' : fields.many2one('product.uom', 'Unit of Measure', required=False),
		'blend_component_ids' : fields.one2many('product.blend.component','blend_id','Components'),
	}

class product_product(osv.Model):
	def get_product_available2(self, cr, uid, ids, context=None):
		""" Finds whether product is available or not in particular warehouse.
		@return: Dictionary of values
		"""
		if context is None:
			context = {}
		location_obj = self.pool.get('stock.location')
		warehouse_obj = self.pool.get('stock.warehouse')
		shop_obj = self.pool.get('sale.shop')
		
		states = context.get('states',[])
		what = context.get('what',())
		if not ids:
			ids = self.search(cr, uid, [])
		res = {}.fromkeys(ids, 0.0)
		if not ids:
			return res

		if context.get('shop', False):
			warehouse_id = shop_obj.read(cr, uid, int(context['shop']), ['warehouse_id'])['warehouse_id'][0]
			if warehouse_id:
				context['warehouse'] = warehouse_id

		if context.get('warehouse', False):
			lot_id = warehouse_obj.read(cr, uid, int(context['warehouse']), ['lot_stock_id'])['lot_stock_id'][0]
			if lot_id:
				context['location'] = lot_id

		if context.get('location', False):
			if type(context['location']) == type(1):
				location_ids = [context['location']]
			elif type(context['location']) in (type(''), type(u'')):
				location_ids = location_obj.search(cr, uid, [('name','ilike',context['location'])], context=context)
			else:
				location_ids = context['location']
		else:
			location_ids = []
			wids = warehouse_obj.search(cr, uid, [], context=context)
			if not wids:
				return res
			for w in warehouse_obj.browse(cr, uid, wids, context=context):
				location_ids.append(w.lot_stock_id.id)

		# build the list of ids of children of the location given by id
		if context.get('compute_child',True):
			child_location_ids = location_obj.search(cr, uid, [('location_id', 'child_of', location_ids)])
			location_ids = child_location_ids or location_ids
		
		# this will be a dictionary of the product UoM by product id
		product2uom = {}
		uom_ids = []
		for product in self.read(cr, uid, ids, ['uom_id'], context=context):
			product2uom[product['id']] = product['uom_id'][0]
			uom_ids.append(product['uom_id'][0])
		# this will be a dictionary of the UoM resources we need for conversion purposes, by UoM id
		uoms_o = {}
		for uom in self.pool.get('product.uom').browse(cr, uid, uom_ids, context=context):
			uoms_o[uom.id] = uom

		results_all_in = []
		results_all_out = []
		results_in = []
		results_out = []
		results_out2 = []
		results_adj_in = []
		results_adj_out = []
		
		from_date = context.get('from_date',False)
		to_date = context.get('to_date',False)
		
		date_str = False
		date_str_in = False
		date_str_out = False
		
		inventory_loss_loc_ids  = self.pool.get('stock.location').search(cr,uid,[('usage','=','inventory')])
		stock_loc_ids = context.get('location', False) and location_ids and location_ids or self.pool.get('stock.location').search(cr,uid,[('usage','=','internal')])
		supp_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','supplier')])
		production_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','production')])
		customer_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','customer')])

		where = [tuple(location_ids),tuple(location_ids),tuple(ids),tuple(states)]
		where_all_in = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_all_out = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_in = [tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_out = [tuple(stock_loc_ids),tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(ids),tuple(states)]
		where_out2 = [tuple(stock_loc_ids),tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(ids),tuple(states)]
		where_adj_in = [tuple(inventory_loss_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]	
		where_adj_out = [tuple(stock_loc_ids),tuple(inventory_loss_loc_ids),tuple(ids),tuple(states)]	

		if from_date and to_date:
			date_str = "date>=%s and date<=%s"
			date_str_in = "date<%s"
			date_str_out = "date<%s"
			where.append(tuple([from_date]))
			where.append(tuple([to_date]))
			where_all_in.append(tuple([from_date]))
			where_all_out.append(tuple([from_date]))
			where_in.append(tuple([from_date]))
			where_in.append(tuple([to_date]))
			where_out.append(tuple([from_date]))
			where_out.append(tuple([to_date]))
			where_out2.append(tuple([from_date]))
			where_out2.append(tuple([to_date]))
			where_adj_in.append(tuple([from_date]))
			where_adj_in.append(tuple([to_date]))
			where_adj_out.append(tuple([from_date]))
			where_adj_out.append(tuple([to_date]))
		
		if 'all_in' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id NOT IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state IN %s ' + (date_str_in and 'and '+date_str_in+' ' or '') +' '\
				'group by product_id,product_uom',tuple(where_all_in))
			results_all_in = cr.fetchall()
		if 'all_out' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id NOT IN %s '\
				'and product_id IN %s '\
				'and state in %s ' + (date_str_out and 'and '+date_str_out+' ' or '') + ' '\
				'group by product_id,product_uom',tuple(where_all_out))
			results_all_out = cr.fetchall()
		if 'in' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by product_id,product_uom',tuple(where_in))
			results_in = cr.fetchall()
		if 'out' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by product_id,product_uom',tuple(where_out))
			results_out = cr.fetchall()
		if 'out2' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by product_id,product_uom',tuple(where_out))
			results_out2 = cr.fetchall()
		if 'adj_in' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by product_id,product_uom',tuple(where_adj_in))
			results_adj_in = cr.fetchall()
		if 'adj_out' in what:
			cr.execute(
				'select sum(product_qty), product_id, product_uom '\
				'from stock_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and product_id IN %s '\
				'and state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by product_id,product_uom',tuple(where_adj_out))
			results_adj_out = cr.fetchall()
		
		# Get the missing UoM resources
		uom_obj = self.pool.get('product.uom')
		uoms = map(lambda x: x[2], results_all_in) + map(lambda x: x[2], results_all_out) + map(lambda x: x[2], results_in)+ map(lambda x: x[2], results_out)+ map(lambda x: x[2], results_out2)+ map(lambda x: x[2], results_adj_in)+ map(lambda x: x[2], results_adj_out)
		if context.get('uom', False):
			uoms += [context['uom']]
		uoms = filter(lambda x: x not in uoms_o.keys(), uoms)
		if uoms:
			uoms = uom_obj.browse(cr, uid, list(set(uoms)), context=context)
			for o in uoms:
				uoms_o[o.id] = o
				
		#TOCHECK: before change uom of product, stock move line are in old uom.
		context.update({'raise-exception': False})
		# Count the incoming quantities
		for quantity, product_id, prod_uom in results_all_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] += quantity
		# Count the outgoing quantities
		for quantity, product_id, prod_uom in results_all_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] -= quantity

		for quantity, product_id, prod_uom in results_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] += quantity
		# Count the outgoing quantities
		for quantity, product_id, prod_uom in results_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] += quantity

		for quantity, product_id, prod_uom in results_out2:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] -= quantity

		for quantity, product_id, prod_uom in results_adj_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] += quantity

		for quantity, product_id, prod_uom in results_adj_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[product_id]], context=context)
			res[product_id] -= quantity

		return res

	def _product_mutation(self, cr, uid, ids, field_names=None, arg=False, context=None):
		if not field_names:
			field_names = []
		if context is None:
			context = {}
		res = {}
		for id in ids:
			res[id] = {}.fromkeys(field_names, 0.0)
		min_date = datetime.now().strftime('%Y-01-01 00:00:00')
		if context.get('from_date',False) and not context.get('to_date',False):
			from_date = context.get('from_date')
			to_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			c.update({'from_date':from_date,'to_date':to_date})
		elif not context.get('from_date',False) and context.get('to_date',False):
			from_date = min_date
			to_date = context.get('to_date',False)
		elif not context.get('from_date',False) and not context.get('to_date',False):
			from_date = min_date
			to_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		else:
			from_date = context.get('from_date')
			to_date = context.get('to_date',False)
		
		for f in field_names:
			c = context.copy()
			c.update({'from_date':from_date,'to_date':to_date})
			if f == 'available_qty':
				c.update({'states': ('done',), 'what': ('all_in', 'all_out') })
			if f == 'opening_qty':
				c.update({'states': ('done',), 'what': ('all_in', 'all_out') })
			if f == 'in_qty':
				c.update({'states': ('done',), 'what': ('in')})
			if f == 'out_qty':
				c.update({'states': ('done',), 'what': ('out'),})
			if f == 'all_qty':
				c.update({'states': ('done',), 'what': ('all_in','all_out','in','out2','adj_in','adj_out'),})
			if f == 'adj_qty':
				c.update({'states': ('done',), 'what': ('adj_in','adj_out'),})	
			stock = self.get_product_available2(cr, uid, ids, context=c)
			for id in ids:
				res[id][f] = stock.get(id, 0.0)
		return res


	_inherit = "product.product"
	_columns = {
		'blend_id' : fields.many2one('product.blend', 'Blend'),
		'raw_material_categ_id' : fields.many2one('product.rm.category', 'Raw Material Category'),
		'product_type' : fields.related('categ_id', 'product_type', type='selection', selection=[
			('finish_good','Barang Jadi'),
			('raw_material','Bahan Baku'),
			# ('auxiliary_material','Auxiliary Materials'),
			# ('tools','Tools and Spares'),
			('waste','Sampah Produksi'),
			# ('asset','Asset'),
			('others','Others'),
			], string='Product Type'),

		'available_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Current On Hand Qty',),

		'opening_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Saldo Awal',),

		'in_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Stock Masuk',),

		'out_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Stock Keluar',),

		'opname_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Opname Qty',),
		
		'all_qty' : fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='On Hand Quantity',),
		
		'adj_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Penyesuaian',),
	}

	def onchange_categ_id(self, cr, uid, ids, categ_id, context=None):
		res = {}
		if categ_id:
			categ = self.pool.get('product.category').browse(cr, uid, categ_id)
			res.update({'product_type':categ.product_type and categ.product_type or False})
			
		return {'value':res}