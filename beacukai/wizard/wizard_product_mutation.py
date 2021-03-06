from openerp.osv import fields,osv
import openerp.addons.decimal_precision as dp
from tools.translate import _
from lxml import etree
from openerp.osv.orm import setup_modifiers
from datetime import datetime
import time

class wizard_product_mutation(osv.osv_memory):
	_name = "wizard.product.mutation"
	_description = "Product Mutation"
	_columns = {
		'from_date': fields.date('From'), 
		'to_date': fields.date('To'),
		'product_type' : fields.selection([
			('finish_good','Barang Jadi'),
			('raw_material','Bahan Baku'),
			# ('auxiliary_material','Auxiliary Materials'),
			# ('tools','Tools and Spares'),
			('waste','Sampah Produksi'),
			# ('asset','Asset'),
			# ('others','Others'),
			], 'Product Type',),
	}

	_defaults = {
		'from_date' : lambda *f : time.strftime('%Y-%m-01'),
		'to_date' : lambda *t : time.strftime('%Y-%m-%d'),
		'product_type' : lambda self, cr, uid, context: context.get('product_type',False),
	}

	def action_open_window(self, cr, uid, ids, context=None):
		""" To open products mutation to given duration/period
		 @param self: The object pointer.
		 @param cr: A database cursor
		 @param uid: ID of the user currently logged in
		 @param ids: An ID or list of IDs (but only the first ID will be processed)
		 @param context: A standard dictionary 
		 @return: dictionary of action act_window product
		"""
		if context is None:
			context = {}
		wizard = self.read(cr, uid, ids, ['from_date', 'to_date','product_type'], context=context)
		if wizard:
			data_obj = self.pool.get('ir.model.data')
			res_model = 'product.product'
			result = data_obj._get_id(cr, uid, 'master_data_custom', 'view_product_tree2_mutation')
			domain = [('product_type','=',wizard[0]['product_type']),('type','<>','service')]
			view_id = data_obj.browse(cr, uid, result).res_id
			
			from_date = wizard[0]['from_date']!=False and \
				datetime.strptime(wizard[0]['from_date'],'%Y-%m-%d').strftime('%Y-%m-%d 00:00:00') or False
			to_date = wizard[0]['to_date'] and \
				datetime.strptime(wizard[0]['to_date'],'%Y-%m-%d').strftime('%Y-%m-%d 23:59:59') or False
			
			return {
				'name': _('Laporan Pertanggungjawaban Mutasi'),
				'view_type': 'form',
				'view_mode': 'tree',
				'res_model': res_model,
				'view_id':[view_id],
				'type': 'ir.actions.act_window',
				'context': {'from_date': from_date or False,
							'to_date': to_date or False,},
				"domain":domain,
			}

wizard_product_mutation()