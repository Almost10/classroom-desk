#!/usr/bin/env python3
"""Create downloadable sample OOXML documents for the no-dependency browser demo."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone

OUTPUT = Path(__file__).resolve().parents[1] / 'local-preview' / 'downloads'
OUTPUT.mkdir(parents=True, exist_ok=True)
NS = {
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties')
ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
ET.register_namespace('dcterms', 'http://purl.org/dc/terms/')
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

def xml(element):
    return ET.tostring(element, encoding='utf-8', xml_declaration=True)

def relationship(rel_id, rel_type, target):
    root=ET.Element('{http://schemas.openxmlformats.org/package/2006/relationships}Relationships')
    ET.SubElement(root,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',{'Id':rel_id,'Type':rel_type,'Target':target})
    return xml(root)

def write_docx():
    W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    ET.register_namespace('w',W)
    document=ET.Element('{%s}document'%W); body=ET.SubElement(document,'{%s}body'%W)
    def paragraph(text,style=None,bold=False):
        p=ET.SubElement(body,'{%s}p'%W)
        if style: ET.SubElement(ET.SubElement(p,'{%s}pPr'%W),'{%s}pStyle'%W,{'{%s}val'%W:style})
        r=ET.SubElement(p,'{%s}r'%W)
        if bold: ET.SubElement(r,'{%s}rPr'%W).append(ET.Element('{%s}b'%W))
        t=ET.SubElement(r,'{%s}t'%W,{'{%s}space'%('http://www.w3.org/XML/1998/namespace'):'preserve'}); t.text=text
    paragraph('TIME VALUE OF MONEY','Title')
    paragraph('Corporate Finance · Illustrative Assignment Draft','Subtitle')
    paragraph('DRAFT FOR REVIEW · Demonstration content only','Heading1')
    paragraph('Present value converts a future cash flow into an equivalent amount today by discounting it using a required rate of return.')
    paragraph('Worked example','Heading1')
    paragraph('Future cash flow: $10,000 · Annual discount rate: 8% · Period: 3 years')
    paragraph('PV = FV / (1 + r)ⁿ = $10,000 / (1.08)³ = $7,938.32')
    paragraph('This example assumes annual compounding and a constant discount rate. Check the method and rounding against your course materials.')
    paragraph('Review notes','Heading1')
    paragraph('Confirm the instructions, course assumptions, sources, calculations and rounding before you use this sample.')
    sect=ET.SubElement(body,'{%s}sectPr'%W)
    ET.SubElement(sect,'{%s}pgSz'%W,{'{%s}w'%W:'12240','{%s}h'%W:'15840'})
    ET.SubElement(sect,'{%s}pgMar'%W,{'{%s}top'%W:'1440','{%s}right'%W:'1440','{%s}bottom'%W:'1440','{%s}left'%W:'1440','{%s}header'%W:'720','{%s}footer'%W:'720','{%s}gutter'%W:'0'})
    types=ET.Element('{http://schemas.openxmlformats.org/package/2006/content-types}Types')
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',{'Extension':'rels','ContentType':'application/vnd.openxmlformats-package.relationships+xml'})
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',{'Extension':'xml','ContentType':'application/xml'})
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',{'PartName':'/word/document.xml','ContentType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'})
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',{'PartName':'/word/styles.xml','ContentType':'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'})
    styles=ET.Element('{%s}styles'%W)
    for sid,name,size in [('Normal','Normal','22'),('Title','Title','44'),('Subtitle','Subtitle','22'),('Heading1','heading 1','30')]:
        style=ET.SubElement(styles,'{%s}style'%W,{'{%s}type'%W:'paragraph','{%s}styleId'%W:sid})
        ET.SubElement(style,'{%s}name'%W,{'{%s}val'%W:name})
        rpr=ET.SubElement(style,'{%s}rPr'%W)
        ET.SubElement(rpr,'{%s}sz'%W,{'{%s}val'%W:size})
    with ZipFile(OUTPUT/'time-value-of-money.docx','w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',xml(types))
        z.writestr('_rels/.rels',relationship('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument','word/document.xml'))
        z.writestr('word/document.xml',xml(document))
        z.writestr('word/styles.xml',xml(styles))
        z.writestr('word/_rels/document.xml.rels',relationship('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles','styles.xml'))

def shape(parent,ident,name,text,x,y,cx,cy,placeholder=None,bullets=False,title=False):
    sp=ET.SubElement(parent,'{%s}sp'%NS['p']); nv=ET.SubElement(sp,'{%s}nvSpPr'%NS['p'])
    ET.SubElement(nv,'{%s}cNvPr'%NS['p'],{'id':str(ident),'name':name}); ET.SubElement(nv,'{%s}cNvSpPr'%NS['p'],{'txBox':'1'}); nvpr=ET.SubElement(nv,'{%s}nvPr'%NS['p'])
    if placeholder: ET.SubElement(nvpr,'{%s}ph'%NS['p'],{'type':placeholder})
    sppr=ET.SubElement(sp,'{%s}spPr'%NS['p']); xf=ET.SubElement(sppr,'{%s}xfrm'%NS['a']); ET.SubElement(xf,'{%s}off'%NS['a'],{'x':str(x),'y':str(y)}); ET.SubElement(xf,'{%s}ext'%NS['a'],{'cx':str(cx),'cy':str(cy)})
    geom=ET.SubElement(sppr,'{%s}prstGeom'%NS['a'],{'prst':'rect'}); ET.SubElement(geom,'{%s}avLst'%NS['a'])
    body=ET.SubElement(sp,'{%s}txBody'%NS['p']); ET.SubElement(body,'{%s}bodyPr'%NS['a'],{'wrap':'square','anchor':'t'}); ET.SubElement(body,'{%s}lstStyle'%NS['a'])
    values=text if isinstance(text,list) else [text]
    for value in values:
        para=ET.SubElement(body,'{%s}p'%NS['a']); ppr=ET.SubElement(para,'{%s}pPr'%NS['a'])
        if bullets and value: ET.SubElement(ppr,'{%s}buChar'%NS['a'],{'char':'•'})
        run=ET.SubElement(para,'{%s}r'%NS['a']); ET.SubElement(run,'{%s}rPr'%NS['a'],{'lang':'en-US','sz':'2900' if title else '2100'}); ET.SubElement(run,'{%s}t'%NS['a']).text=value
        ET.SubElement(para,'{%s}endParaRPr'%NS['a'],{'lang':'en-US'})

def slide(title,lines):
    root=ET.Element('{%s}sld'%NS['p'],{'showMasterSp':'1'}); c=ET.SubElement(root,'{%s}cSld'%NS['p'],{'name':title[:50]}); tree=ET.SubElement(c,'{%s}spTree'%NS['p'])
    nv=ET.SubElement(tree,'{%s}nvGrpSpPr'%NS['p']); ET.SubElement(nv,'{%s}cNvPr'%NS['p'],{'id':'1','name':''}); ET.SubElement(nv,'{%s}cNvGrpSpPr'%NS['p']); ET.SubElement(nv,'{%s}nvPr'%NS['p'])
    xf=ET.SubElement(tree,'{%s}grpSpPr'%NS['p']); inner=ET.SubElement(xf,'{%s}xfrm'%NS['a']); ET.SubElement(inner,'{%s}off'%NS['a'],{'x':'0','y':'0'}); ET.SubElement(inner,'{%s}ext'%NS['a'],{'cx':'0','cy':'0'}); ET.SubElement(inner,'{%s}chOff'%NS['a'],{'x':'0','y':'0'}); ET.SubElement(inner,'{%s}chExt'%NS['a'],{'cx':'0','cy':'0'})
    shape(tree,2,'Title',title,950000,600000,10600000,1200000,placeholder='title',title=True)
    shape(tree,3,'Content',lines,1100000,2100000,10000000,4300000,placeholder='body',bullets=True)
    ET.SubElement(root,'{%s}clrMapOvr'%NS['p']).append(ET.Element('{%s}masterClrMapping'%NS['a']))
    return xml(root)

def write_pptx():
    P='http://schemas.openxmlformats.org/presentationml/2006/main'; A=NS['a']
    types=ET.Element('{http://schemas.openxmlformats.org/package/2006/content-types}Types')
    ct='http://schemas.openxmlformats.org/package/2006/content-types'
    for ext,mime in [('rels','application/vnd.openxmlformats-package.relationships+xml'),('xml','application/xml')]: ET.SubElement(types,'{%s}Default'%ct,{'Extension':ext,'ContentType':mime})
    overrides=[('/ppt/presentation.xml','application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),('/ppt/slides/slide1.xml','application/vnd.openxmlformats-officedocument.presentationml.slide+xml'),('/ppt/slideLayouts/slideLayout1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'),('/ppt/slideMasters/slideMaster1.xml','application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml'),('/ppt/theme/theme1.xml','application/vnd.openxmlformats-officedocument.theme+xml')]
    for part,mime in overrides: ET.SubElement(types,'{%s}Override'%ct,{'PartName':part,'ContentType':mime})
    pres=ET.Element('{%s}presentation'%P); ids=ET.SubElement(pres,'{%s}sldIdLst'%P); ET.SubElement(ids,'{%s}sldId'%P,{'id':'256','{%s}id'%NS['r']:'rId1'}); ET.SubElement(pres,'{%s}sldSz'%P,{'cx':'12192000','cy':'6858000','type':'wide'}); ET.SubElement(pres,'{%s}notesSz'%P,{'cx':'6858000','cy':'9144000'})
    presrels=ET.Element('{http://schemas.openxmlformats.org/package/2006/relationships}Relationships'); ET.SubElement(presrels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',{'Id':'rId1','Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide','Target':'slides/slide1.xml'}); ET.SubElement(presrels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',{'Id':'rId2','Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster','Target':'slideMasters/slideMaster1.xml'})
    master=ET.Element('{%s}sldMaster'%P); mc=ET.SubElement(master,'{%s}cSld'%P); mt=ET.SubElement(mc,'{%s}spTree'%P); mvg=ET.SubElement(mt,'{%s}nvGrpSpPr'%P); ET.SubElement(mvg,'{%s}cNvPr'%P,{'id':'1','name':''}); ET.SubElement(mvg,'{%s}cNvGrpSpPr'%P); ET.SubElement(mvg,'{%s}nvPr'%P); mg=ET.SubElement(mt,'{%s}grpSpPr'%P); mxf=ET.SubElement(mg,'{%s}xfrm'%A)
    for tag in ('off','ext','chOff','chExt'): ET.SubElement(mxf,'{%s}%s'%(A,tag),{'x':'0','y':'0'} if tag in ('off','chOff') else {'cx':'0','cy':'0'})
    ET.SubElement(master,'{%s}clrMap'%P,{'bg1':'lt1','tx1':'dk1','bg2':'lt2','tx2':'dk2','accent1':'accent1','accent2':'accent2','accent3':'accent3','accent4':'accent4','accent5':'accent5','accent6':'accent6','hlink':'hlink','folHlink':'folHlink'})
    layouts=ET.SubElement(master,'{%s}sldLayoutIdLst'%P); ET.SubElement(layouts,'{%s}sldLayoutId'%P,{'id':'1','{%s}id'%NS['r']:'rId1'})
    txstyles=ET.SubElement(master,'{%s}txStyles'%P)
    for name in ('titleStyle','bodyStyle','otherStyle'):
        style=ET.SubElement(txstyles,'{%s}%s'%(P,name)); level=ET.SubElement(style,'{%s}lvl1pPr'%A); ET.SubElement(level,'{%s}defRPr'%A)
    layout=ET.Element('{%s}sldLayout'%P,{'type':'blank','preserve':'1'}); lc=ET.SubElement(layout,'{%s}cSld'%P); lt=ET.SubElement(lc,'{%s}spTree'%P); lvg=ET.SubElement(lt,'{%s}nvGrpSpPr'%P); ET.SubElement(lvg,'{%s}cNvPr'%P,{'id':'1','name':''}); ET.SubElement(lvg,'{%s}cNvGrpSpPr'%P); ET.SubElement(lvg,'{%s}nvPr'%P); lg=ET.SubElement(lt,'{%s}grpSpPr'%P); lxf=ET.SubElement(lg,'{%s}xfrm'%A)
    for tag in ('off','ext','chOff','chExt'): ET.SubElement(lxf,'{%s}%s'%(A,tag),{'x':'0','y':'0'} if tag in ('off','chOff') else {'cx':'0','cy':'0'})
    ET.SubElement(layout,'{%s}clrMapOvr'%P).append(ET.Element('{%s}masterClrMapping'%A))
    theme=ET.Element('{%s}theme'%A,{'name':'Classroom Desk'}); elems=ET.SubElement(theme,'{%s}themeElements'%A); colors=ET.SubElement(elems,'{%s}clrScheme'%A,{'name':'Classroom Desk'}); colormap={'dk1':('sysClr',{'val':'windowText','lastClr':'15241D'}),'lt1':('sysClr',{'val':'window','lastClr':'F6F7F1'}),'dk2':('srgbClr',{'val':'314639'}),'lt2':('srgbClr',{'val':'FFFFFF'}),'accent1':('srgbClr',{'val':'456C50'}),'accent2':('srgbClr',{'val':'B6CE93'}),'accent3':('srgbClr',{'val':'B7945E'}),'accent4':('srgbClr',{'val':'6A8EA0'}),'accent5':('srgbClr',{'val':'8F7DA2'}),'accent6':('srgbClr',{'val':'7D9180'}),'hlink':('srgbClr',{'val':'426B91'}),'folHlink':('srgbClr',{'val':'755575'})}
    for name,(kind,attrs) in colormap.items(): ET.SubElement(colors,'{%s}%s'%(A,name)).append(ET.Element('{%s}%s'%(A,kind),attrs))
    fonts=ET.SubElement(elems,'{%s}fontScheme'%A,{'name':'Classroom Desk'})
    for name,major in (('majorFont',True),('minorFont',False)):
        font=ET.SubElement(fonts,'{%s}%s'%(A,name)); ET.SubElement(font,'{%s}latin'%A,{'typeface':'Aptos Display' if major else 'Aptos'}); ET.SubElement(font,'{%s}ea'%A,{'typeface':''}); ET.SubElement(font,'{%s}cs'%A,{'typeface':''})
    fmt=ET.SubElement(elems,'{%s}fmtScheme'%A,{'name':'Classroom Desk'})
    fills=ET.SubElement(fmt,'{%s}fillStyleLst'%A)
    for _ in range(3):
        sf=ET.SubElement(fills,'{%s}solidFill'%A); ET.SubElement(sf,'{%s}schemeClr'%A,{'val':'phClr'})
    lines=ET.SubElement(fmt,'{%s}lnStyleLst'%A)
    for width in ('6350','12700','19050'):
        line=ET.SubElement(lines,'{%s}ln'%A,{'w':width,'cap':'flat','cmpd':'sng','algn':'ctr'}); sf=ET.SubElement(line,'{%s}solidFill'%A); ET.SubElement(sf,'{%s}schemeClr'%A,{'val':'phClr'}); ET.SubElement(line,'{%s}prstDash'%A,{'val':'solid'}); ET.SubElement(line,'{%s}miter'%A,{'lim':'800000'})
    effects=ET.SubElement(fmt,'{%s}effectStyleLst'%A)
    for _ in range(3): ET.SubElement(effects,'{%s}effectStyle'%A).append(ET.Element('{%s}effectLst'%A))
    bg=ET.SubElement(fmt,'{%s}bgFillStyleLst'%A)
    for _ in range(3):
        fill=ET.SubElement(bg,'{%s}solidFill'%A); ET.SubElement(fill,'{%s}schemeClr'%A,{'val':'phClr'})
    relroot='http://schemas.openxmlformats.org/package/2006/relationships'
    masterrels=ET.Element('{%s}Relationships'%relroot); ET.SubElement(masterrels,'{%s}Relationship'%relroot,{'Id':'rId1','Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout','Target':'../slideLayouts/slideLayout1.xml'}); ET.SubElement(masterrels,'{%s}Relationship'%relroot,{'Id':'rId2','Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme','Target':'../theme/theme1.xml'})
    layoutrels=relationship('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster','../slideMasters/slideMaster1.xml')
    sliderels=relationship('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout','../slideLayouts/slideLayout1.xml')
    with ZipFile(OUTPUT/'time-value-of-money.pptx','w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',xml(types)); z.writestr('_rels/.rels',relationship('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument','ppt/presentation.xml'))
        z.writestr('ppt/presentation.xml',xml(pres)); z.writestr('ppt/_rels/presentation.xml.rels',xml(presrels)); z.writestr('ppt/slides/slide1.xml',slide('Present value',['Money today can earn a return.','Discounting makes future cash flows comparable with cash today.','Formula: PV = FV / (1 + r)ⁿ','Example: $10,000 / (1.08)³ = $7,938.32.']))
        z.writestr('ppt/slides/_rels/slide1.xml.rels',sliderels); z.writestr('ppt/slideLayouts/slideLayout1.xml',xml(layout)); z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels',layoutrels)
        z.writestr('ppt/slideMasters/slideMaster1.xml',xml(master)); z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels',xml(masterrels)); z.writestr('ppt/theme/theme1.xml',xml(theme))

if __name__=='__main__':
    write_docx(); write_pptx()
    print('Created sample files in local-preview/downloads/. These are only for the offline demo.')
