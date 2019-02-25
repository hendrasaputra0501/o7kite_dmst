from openerp.osv import fields,osv
import openerp.addons.decimal_precision as dp
from tools.translate import _
from lxml import etree
from openerp.osv.orm import setup_modifiers
from datetime import datetime
import time

class wizard_product_outgoing(osv.osv_memory):
	_name = "wizard.product.outgoing"
	_description = "Product outgoing"
	_columns = {
		'from_date': fields.date('From'), 
		'to_date': fields.date('To'),
		'shipment_type' : fields.selection([('in','Incoming Goods'),('out','Sending Goods')],'Shipment Type'),
		'product_type' : fields.selection([
			('finish_good','Barang Jadi'),
			('raw_material','Bahan Baku'),
			('auxiliary_material','Bahan Penolong'),
			('tools','Alat-alat'),
			('waste','Sampah Produksi'),
			('asset','Aset'),
			('others','Lain - lain'),
			], 'Product Type',),
	}

	_defaults = {
		'from_date' : lambda *f : time.strftime('%Y-%m-01'),
		'to_date' : lambda *t : time.strftime('%Y-%m-%d'),
		'product_type' : lambda self, cr, uid, context: context.get('product_type',False),
		'shipment_type' : lambda self, cr, uid, context: context.get('shipment_type',False),
	}

	def action_open_window(self, cr, uid, ids, context=None):
		""" To open products outgoing to given duration/period
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
			res_model = 'beacukai.document.line.out'
			result = data_obj._get_id(cr, uid, 'beacukai', 'view_beacukai_document_line_out_tree')
			domain = [('shipment_type','=','out'),('state','=','validated')]
			view_id = data_obj.browse(cr, uid, result).res_id
			
			from_date = wizard[0]['from_date']!=False and \
				datetime.strptime(wizard[0]['from_date'],'%Y-%m-%d').strftime('%Y-%m-%d 00:00:00') or False
			to_date = wizard[0]['to_date'] and \
				datetime.strptime(wizard[0]['to_date'],'%Y-%m-%d').strftime('%Y-%m-%d 23:59:59') or False
			
			domain.append(('registration_date','>=', wizard[0]['from_date']))
			domain.append(('registration_date','<=', wizard[0]['to_date']))
			return {
				'name': _('Laporan Pengeluaran Hasil Produksi'),
				'view_type': 'form',
				'view_mode': 'tree',
				'res_model': res_model,
				'view_id':[view_id],
				'type': 'ir.actions.act_window',
				'context': {},
				"domain":domain,
			}

	def export_excel(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		wizard = self.browse(cr,uid,ids,context)[0]
		datas = {
			'model': 'wizard.product.outgoing',
			'from_date' : wizard.from_date,
			'to_date' : wizard.to_date,
			'product_type':wizard.product_type,
			'shipment_type':wizard.shipment_type,
			}
		
		return {
				'type': 'ir.actions.report.xml',
				'report_name': 'beacukai.out.form.xls',
				'report_type': 'xls',
				'datas': datas,
				}
wizard_product_outgoing()