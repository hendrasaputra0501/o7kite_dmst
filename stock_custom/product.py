import math
import re

from openerp import tools, SUPERUSER_ID
from openerp.osv import osv, fields, expression
from openerp.tools.translate import _

import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_round
from datetime import datetime
import time

class product_rm_categ(osv.Model):
	def get_product_available(self, cr, uid, ids, context=None):
		""" Finds whether product is available or not in particular warehouse.
		@return: Dictionary of values
		"""
		if context is None:
			context = {}
		location_obj = self.pool.get('stock.location')
		warehouse_obj = self.pool.get('stock.warehouse')
		shop_obj = self.pool.get('sale.shop')
		
		states = context.get('states',['done'])
		# states = ['done']
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
		for product in self.read(cr, uid, ids, ['product_uom'], context=context):
			product2uom[product['id']] = product['product_uom'][0]
			uom_ids.append(product['product_uom'][0])
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
		# production
		results_prod_all_in = []
		results_prod_all_out = []
		results_prod_in = []
		results_prod_out = []
		results_prod_out2 = []
		results_prod_waste = []
		results_prod_waste2 = []
		results_prod_adj_in = []
		results_prod_adj_out = []

		from_date = context.get('from_date',False)
		to_date = context.get('to_date',False)
		
		date_str = False
		date_str_in = False
		date_str_out = False
		
		inventory_loss_loc_ids  = self.pool.get('stock.location').search(cr,uid,[('usage','=','inventory'),('scrap_location','=',False)])
		waste_loc_ids  = self.pool.get('stock.location').search(cr,uid,[('usage','=','inventory'),('scrap_location','=',True)])
		stock_loc_ids = context.get('location', False) and location_ids and location_ids or self.pool.get('stock.location').search(cr,uid,[('usage','=','internal')])
		supp_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','supplier')])
		production_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','production')])
		customer_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','customer')])

		where = [tuple(location_ids),tuple(location_ids),tuple(ids),tuple(states)]
		where_all_in = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_all_out = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_in = [tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_out = [tuple(stock_loc_ids),tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(ids),tuple(states)]
		where_adj_in = [tuple(inventory_loss_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_adj_out = [tuple(stock_loc_ids),tuple(inventory_loss_loc_ids),tuple(ids),tuple(states)]
		# production
		where_prod_all_in = [tuple(production_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_all_out = [tuple(production_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_in = [tuple(stock_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_out = [tuple(production_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_prod_waste = [tuple(production_loc_ids),tuple(waste_loc_ids),tuple(ids),tuple(states)]
		where_prod_adj_in = [tuple(inventory_loss_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_adj_out = [tuple(production_loc_ids),tuple(inventory_loss_loc_ids),tuple(ids),tuple(states)]

		if from_date and to_date:
			date_str = "sm.date>=%s and sm.date<=%s"
			date_str_in = "sm.date<%s"
			date_str_out = "sm.date<%s"

			prod_date_str = "date_done>=%s and date_done<=%s"
			prod_date_str_in = "date_done<%s"
			prod_date_str_out = "date_done<%s"
			
			where.append(tuple([from_date]))
			where.append(tuple([to_date]))
			where_all_in.append(tuple([from_date]))
			where_all_out.append(tuple([from_date]))
			where_in.append(tuple([from_date]))
			where_in.append(tuple([to_date]))
			where_out.append(tuple([from_date]))
			where_out.append(tuple([to_date]))
			where_adj_in.append(tuple([from_date]))
			where_adj_in.append(tuple([to_date]))
			where_adj_out.append(tuple([from_date]))
			where_adj_out.append(tuple([to_date]))
			# production
			where_prod_all_in.append(tuple([from_date]))
			where_prod_all_out.append(tuple([from_date]))
			where_prod_in.append(tuple([from_date]))
			where_prod_in.append(tuple([to_date]))
			where_prod_out.append(tuple([from_date]))
			where_prod_out.append(tuple([to_date]))
			where_prod_waste.append(tuple([from_date]))
			where_prod_waste.append(tuple([to_date]))
			where_prod_adj_in.append(tuple([from_date]))
			where_prod_adj_in.append(tuple([to_date]))
			where_prod_adj_out.append(tuple([from_date]))
			where_prod_adj_out.append(tuple([to_date]))

		
		if 'all_in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id ' \
				'where sm.location_id NOT IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state IN %s ' + (date_str_in and 'and '+date_str_in+' ' or '') +' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_all_in))
			results_all_in = cr.fetchall()
		if 'all_out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id NOT IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state in %s ' + (date_str_out and 'and '+date_str_out+' ' or '') + ' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_all_out))
			results_all_out = cr.fetchall()
		if 'in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_in))
			results_in = cr.fetchall()
		if 'out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_out))
			results_out = cr.fetchall()
		if 'out2' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_out))
			results_out2 = cr.fetchall()
		if 'adj_in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_adj_in))
			results_adj_in = cr.fetchall()
		if 'adj_out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.raw_material_categ_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.raw_material_categ_id is not NULL '\
				'and pp.raw_material_categ_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.raw_material_categ_id,sm.product_uom',tuple(where_adj_out))
			results_adj_out = cr.fetchall()

		# production
		if 'prod_all_IN' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id NOT IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state IN %s ' + (prod_date_str_in and 'and '+prod_date_str_in+' ' or '') +' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_all_in))
			results_prod_all_in = cr.fetchall()
		if 'prod_all_OUT' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id NOT IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str_out and 'and '+prod_date_str_out+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_all_out))
			results_prod_all_out = cr.fetchall()
		if 'prod_IN' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state IN %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') +' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_in))
			results_prod_in = cr.fetchall()
		if 'prod_OUT' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_out))
			results_prod_out = cr.fetchall()

		if 'prod_OUT2' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_out))
			results_prod_out2 = cr.fetchall()

		if 'prod_waste' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_waste))
			results_prod_waste = cr.fetchall()

		if 'prod_waste2' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_waste))
			results_prod_waste2 = cr.fetchall()

		if 'prod_adj_IN3' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state IN %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') +' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_adj_in))
			results_prod_adj_in = cr.fetchall()
		
		if 'prod_adj_OUT3' in what:
			cr.execute(
				'select sum(product_qty), raw_material_categ_id, product_uom '\
				'from production_move '\
				'where location_id IN %s '\
				'and location_dest_id IN %s '\
				'and raw_material_categ_id IN %s '\
				'and state in %s ' + (prod_date_str and 'and '+prod_date_str+' ' or '') + ' '\
				'group by raw_material_categ_id,product_uom',tuple(where_prod_adj_out))
			results_prod_adj_out = cr.fetchall()
		
		# Get the missing UoM resources
		uom_obj = self.pool.get('product.uom')
		uoms = map(lambda x: x[2], results_all_in) + map(lambda x: x[2], results_all_out) + map(lambda x: x[2], results_in)+ \
				map(lambda x: x[2], results_out)+ map(lambda x: x[2], results_out2)+ map(lambda x: x[2], results_adj_in)+ \
				map(lambda x: x[2], results_adj_out) + map(lambda x: x[2], results_prod_all_out) + map(lambda x: x[2], results_prod_all_in) + \
				map(lambda x: x[2], results_prod_in) + map(lambda x: x[2], results_prod_out) + map(lambda x: x[2], results_prod_out2) + \
				map(lambda x: x[2], results_prod_waste) + map(lambda x: x[2], results_prod_waste2) + map(lambda x: x[2], results_prod_adj_in) + \
				map(lambda x: x[2], results_prod_adj_out)
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
		for quantity, raw_material_categ_id, prod_uom in results_all_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity
		# Count the outgoing quantities
		for quantity, raw_material_categ_id, prod_uom in results_all_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		for quantity, raw_material_categ_id, prod_uom in results_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity
		# Count the outgoing quantities
		for quantity, raw_material_categ_id, prod_uom in results_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity

		for quantity, raw_material_categ_id, prod_uom in results_out2:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		for quantity, raw_material_categ_id, prod_uom in results_adj_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity

		for quantity, raw_material_categ_id, prod_uom in results_adj_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		# production
		for quantity, raw_material_categ_id, prod_uom in results_prod_all_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity
		# Count the outgoing quantities
		for quantity, raw_material_categ_id, prod_uom in results_prod_all_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity
		# Count the outgoing quantities
		for quantity, raw_material_categ_id, prod_uom in results_prod_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_out2:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_waste:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_waste2:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_adj_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] += quantity

		for quantity, raw_material_categ_id, prod_uom in results_prod_adj_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[raw_material_categ_id]], context=context)
			res[raw_material_categ_id] -= quantity
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

			if f == 'prod_opening_qty':
				c.update({'states': ('done',), 'what': ('prod_all_IN', 'prod_all_OUT') })
			if f == 'prod_in_qty':
				c.update({'states': ('done',), 'what': ('prod_IN')})
			if f == 'prod_out_qty':
				c.update({'states': ('done',), 'what': ('prod_OUT'),})
			if f == 'prod_waste_qty':
				c.update({'states': ('done',), 'what': ('prod_waste'),})
			if f == 'prod_all_qty':
				c.update({'states': ('done',), 'what': ('prod_all_IN','prod_all_OUT','prod_IN','prod_OUT2','prod_waste2','prod_adj_IN3','prod_adj_OUT3'),})
			if f == 'prod_adj_qty':
				c.update({'states': ('done',), 'what': ('prod_adj_IN3','prod_adj_OUT3'),})

			stock = self.get_product_available(cr, uid, ids, context=c)
			for id in ids:
				res[id][f] = stock.get(id, 0.0)
		return res

	_inherit = "product.rm.category"
	_columns = {
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

		'prod_opening_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='BDP Awal',),

		'prod_in_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Penerimaan',),

		'prod_out_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Hasil Produksi',),

		'prod_waste_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Waste',),

		'prod_opname_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='BDP Opname',),
		
		'prod_all_qty' : fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='On Hand BDP',),
		
		'prod_adj_qty': fields.function(_product_mutation, multi='qty_mutation',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Penyesuaian BDP',),
	}

class product_blend(osv.Model):
	def get_product_available(self, cr, uid, ids, context=None):
		""" Finds whether product is available or not in particular warehouse.
		@return: Dictionary of values
		"""
		if context is None:
			context = {}
		location_obj = self.pool.get('stock.location')
		warehouse_obj = self.pool.get('stock.warehouse')
		shop_obj = self.pool.get('sale.shop')
		
		states = context.get('states',['done'])
		# states = ['done']
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
		for product in self.read(cr, uid, ids, ['product_uom'], context=context):
			product2uom[product['id']] = product['product_uom'][0]
			uom_ids.append(product['product_uom'][0])
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
		# production
		results_prod_all_in = []
		results_prod_all_out = []
		results_prod_in = []
		results_prod_out = []
		results_prod_out2 = []
		results_prod_waste = []
		results_prod_waste2 = []
		results_prod_adj_in = []
		results_prod_adj_out = []

		from_date = context.get('from_date',False)
		to_date = context.get('to_date',False)
		
		date_str = False
		date_str_in = False
		date_str_out = False
		
		inventory_loss_loc_ids  = self.pool.get('stock.location').search(cr,uid,[('usage','=','inventory'),('scrap_location','=',False)])
		waste_loc_ids  = self.pool.get('stock.location').search(cr,uid,[('usage','=','inventory'),('scrap_location','=',True)])
		stock_loc_ids = context.get('location', False) and location_ids and location_ids or self.pool.get('stock.location').search(cr,uid,[('usage','=','internal')])
		supp_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','supplier')])
		production_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','production')])
		customer_loc_ids = self.pool.get('stock.location').search(cr,uid,[('usage','=','customer')])

		where = [tuple(location_ids),tuple(location_ids),tuple(ids),tuple(states)]
		where_all_in = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_all_out = [tuple(stock_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_in = [tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_out = [tuple(stock_loc_ids),tuple(supp_loc_ids+production_loc_ids+customer_loc_ids),tuple(ids),tuple(states)]
		where_adj_in = [tuple(inventory_loss_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]	
		where_adj_out = [tuple(stock_loc_ids),tuple(inventory_loss_loc_ids),tuple(ids),tuple(states)]	
		# production
		where_prod_all_in = [tuple(production_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_all_out = [tuple(production_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_in = [tuple(stock_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_out = [tuple(production_loc_ids),tuple(stock_loc_ids),tuple(ids),tuple(states)]
		where_prod_waste = [tuple(production_loc_ids),tuple(waste_loc_ids),tuple(ids),tuple(states)]
		where_prod_adj_in = [tuple(inventory_loss_loc_ids),tuple(production_loc_ids),tuple(ids),tuple(states)]
		where_prod_adj_out = [tuple(production_loc_ids),tuple(inventory_loss_loc_ids),tuple(ids),tuple(states)]

		if from_date and to_date:
			date_str = "sm.date>=%s and sm.date<=%s"
			date_str_in = "sm.date<%s"
			date_str_out = "sm.date<%s"
			where.append(tuple([from_date]))
			where.append(tuple([to_date]))
			where_all_in.append(tuple([from_date]))
			where_all_out.append(tuple([from_date]))
			where_in.append(tuple([from_date]))
			where_in.append(tuple([to_date]))
			where_out.append(tuple([from_date]))
			where_out.append(tuple([to_date]))
			where_adj_in.append(tuple([from_date]))
			where_adj_in.append(tuple([to_date]))
			where_adj_out.append(tuple([from_date]))
			where_adj_out.append(tuple([to_date]))
			# production
			where_prod_all_in.append(tuple([from_date]))
			where_prod_all_out.append(tuple([from_date]))
			where_prod_in.append(tuple([from_date]))
			where_prod_in.append(tuple([to_date]))
			where_prod_out.append(tuple([from_date]))
			where_prod_out.append(tuple([to_date]))
			where_prod_waste.append(tuple([from_date]))
			where_prod_waste.append(tuple([to_date]))
			where_prod_adj_in.append(tuple([from_date]))
			where_prod_adj_in.append(tuple([to_date]))
			where_prod_adj_out.append(tuple([from_date]))
			where_prod_adj_out.append(tuple([to_date]))
		# print "??????????????????", what, 'in' in what
		if 'all_in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id NOT IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state IN %s ' + (date_str_in and 'and '+date_str_in+' ' or '') +' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_all_in))
			results_all_in = cr.fetchall()
		if 'all_out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id NOT IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state in %s ' + (date_str_out and 'and '+date_str_out+' ' or '') + ' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_all_out))
			results_all_out = cr.fetchall()
		if 'in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_in))
			results_in = cr.fetchall()
		if 'out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_out))
			results_out = cr.fetchall()
		if 'out2' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_out))
			results_out2 = cr.fetchall()
		if 'adj_in' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state IN %s ' + (date_str and 'and '+date_str+' ' or '') +' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_adj_in))
			results_adj_in = cr.fetchall()
		if 'adj_out' in what:
			cr.execute(
				'select sum(sm.product_qty), pp.blend_id, sm.product_uom '\
				'from stock_move sm '\
				'inner join product_product pp on pp.id=sm.product_id '\
				'where sm.location_id IN %s '\
				'and sm.location_dest_id IN %s '\
				'and pp.blend_id is not NULL '\
				'and pp.blend_id IN %s '\
				'and sm.state in %s ' + (date_str and 'and '+date_str+' ' or '') + ' '\
				'group by pp.blend_id,sm.product_uom',tuple(where_adj_out))
			results_adj_out = cr.fetchall()
		# Get the missing UoM resources
		uom_obj = self.pool.get('product.uom')
		uoms = map(lambda x: x[2], results_all_in) + map(lambda x: x[2], results_all_out) + map(lambda x: x[2], results_in)+ \
				map(lambda x: x[2], results_out)+ map(lambda x: x[2], results_out2)+ map(lambda x: x[2], results_adj_in)+ \
				map(lambda x: x[2], results_adj_out)
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
		for quantity, blend_id, prod_uom in results_all_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_all_in", quantity, blend_id, prod_uom
			res[blend_id] += quantity
		# Count the outgoing quantities
		for quantity, blend_id, prod_uom in results_all_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_all_out", quantity, blend_id, prod_uom
			res[blend_id] -= quantity

		for quantity, blend_id, prod_uom in results_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					 uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_in", quantity, blend_id, prod_uom
			res[blend_id] += quantity
		# Count the outgoing quantities
		for quantity, blend_id, prod_uom in results_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_out", quantity, blend_id, prod_uom
			res[blend_id] += quantity

		for quantity, blend_id, prod_uom in results_out2:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_out2", quantity, blend_id, prod_uom
			res[blend_id] -= quantity

		for quantity, blend_id, prod_uom in results_adj_in:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_adj_in", quantity, blend_id, prod_uom
			res[blend_id] += quantity

		for quantity, blend_id, prod_uom in results_adj_out:
			quantity = uom_obj._compute_qty_obj(cr, uid, uoms_o[prod_uom], quantity,
					uoms_o[context.get('uom', False) or product2uom[blend_id]], context=context)
			# print ":::::::::::::::::results_adj_out", quantity, blend_id, prod_uom
			res[blend_id] -= quantity
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

			stock = self.get_product_available(cr, uid, ids, context=c)
			for id in ids:
				res[id][f] = stock.get(id, 0.0)
		return res

	_inherit = "product.blend"
	_columns = {
		'ratio_produced_qty' : fields.float('Ratio Produced Qty', digits_compute= dp.get_precision('Product Unit of Measure')),
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