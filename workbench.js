/* DOM-only workbench: retains original control nodes, handlers and canvas pixels. */
window.ObserverWorkbench = (()=>{
  const byId=id=>document.getElementById(id);
  let zoom=1,workspace,panels,zoomLabel,previewObserver,resizeFrame=0,controller=null;
  let layoutKey=null,layoutAspect=null,activeGroup=0,operation=null,pendingFocus=null,orb,orbStatus,previousBox,nextBox,markers=[],lockedNodes=[];
  let sidebar,globalActions,sheetHeader,sheetTitle,sheetToggle,parameterScroll,sheetObserver,sheetFrame=0,viewDeferred=false;
  const layoutPointers=new Set();
  let orbOrigin,orbLine,mobileSaveURL=null;
  const mobile=()=>matchMedia('(max-width:820px), (pointer:coarse) and (max-width:1100px)').matches;
  function icon(path) {const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('width','16');s.setAttribute('height','16');s.setAttribute('fill','none');s.setAttribute('stroke','currentColor');s.setAttribute('stroke-width','1.6');s.setAttribute('aria-hidden','true');const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',path);s.append(p);return s;}
  function button(id,text,path,action) {const b=document.createElement('button');b.id=id;b.type='button';b.title=text;b.setAttribute('aria-label',text);b.append(icon(path),document.createTextNode(text));if(action)b.onclick=action;return b;}
  const boxSpace=(element,axis)=>{
    const css=getComputedStyle(element),sides=axis==='x'?['Left','Right']:['Top','Bottom'];
    return sides.reduce((sum,side)=>sum+(parseFloat(css['padding'+side])||0)+(parseFloat(css['border'+side+'Width'])||0),0);
  };
  function paneMetrics(panel) {
    const preview=panel.querySelector('.preview'),info=panel.querySelector('.image-info'),css=getComputedStyle(info);
    return {x:boxSpace(panel,'x')+boxSpace(preview,'x')+2,
      y:boxSpace(panel,'y')+boxSpace(preview,'y')+panel.querySelector('h2').getBoundingClientRect().height+
        info.getBoundingClientRect().height+(parseFloat(css.marginTop)||0)+(parseFloat(css.marginBottom)||0)+2};
  }
  function chooseLayout() {
    const canvas=byId('output'),hint=byId('layoutInfo');
    if(mobile()||canvas.hidden){panels.dataset.layout='side';layoutKey=layoutAspect=null;if(hint)hint.textContent='左右对照';return;}
    const r=panels.getBoundingClientRect(),css=getComputedStyle(panels),ratio=canvas.width/canvas.height;
    const key=[r.width.toFixed(2),r.height.toFixed(2),ratio].join(':');if(key===layoutKey)return;
    layoutKey=key;
    const width=r.width-boxSpace(panels,'x'),height=r.height-boxSpace(panels,'y');
    const gapX=parseFloat(css.columnGap)||0,gapY=parseFloat(css.rowGap)||0;
    const metrics=Array.from(panels.querySelectorAll('.panel'),paneMetrics);
    const area=(w,h,m)=>{const fit=Math.max(0,Math.min(w-m.x,(h-m.y)*ratio));return fit*fit/ratio;};
    const side=area((width-gapX)*.34,height,metrics[0])+1.25*area((width-gapX)*.66,height,metrics[1]);
    const stack=area(width,(height-gapY)*.42,metrics[0])+1.25*area(width,(height-gapY)*.58,metrics[1]);
    const threshold=ratio>1.65?.75:1;
    const previous=layoutAspect===ratio?panels.dataset.layout:null;
    // A dead band retains the current layout near a tie; layout never depends
    // on the CSS size of the scaled canvas or on whether scrollbars are present.
    const preferStack=ratio>=.96&&stack>side*threshold*(previous==='stack'?.92:previous==='side'?1.08:1);
    panels.dataset.layout=preferStack?'stack':'side';layoutAspect=ratio;
    if(hint)hint.textContent=preferStack?'上下对照':'左右对照';
  }
  function refreshInfo() {
    if(!panels)return;
    const source=byId('original'),output=byId('output'),ready=!source.hidden&&!output.hidden;
    const values={sourceFileName:ready?(source.dataset.filename||'已上传图片'):'未上传图片',outputFileName:'PNG 输出',
      sourceDimensions:ready?`${source.width} × ${source.height}`:'—',outputDimensions:ready?`${output.width} × ${output.height}`:'—',
      sourceState:ready?'原始':'待上传',outputState:ready?'就绪':'待上传'};
    for(const [id,value] of Object.entries(values)){const node=byId(id);if(node&&node.textContent!==value){node.textContent=value;node.title=value;}}
  }
  // The sheet measures natural tool content, not its constrained scroll viewport.
  // Nothing here writes canvas pixels or calls image analysis.
  function interactionBusy() {return !!operation||!!pendingFocus||layoutPointers.size>0;}
  function updateSheet() {
    if(!sidebar)return;
    const phone=mobile(),root=byId('workbench');
    if(phone&&globalActions.parentElement!==root)root.prepend(globalActions);
    else if(!phone&&globalActions.parentElement!==sidebar)sidebar.prepend(globalActions);
    if(!phone){sidebar.style.removeProperty('--sheet-height');return;}
    if(interactionBusy()){viewDeferred=true;return;}
    const group=byId('parameterGroup'+activeGroup),nav=sidebar.querySelector('.function-navigation');
    const content=group.getBoundingClientRect().height+boxSpace(parameterScroll,'y');
    const chrome=sheetHeader.getBoundingClientRect().height+nav.getBoundingClientRect().height+boxSpace(sidebar,'y');
    const viewport=Math.min(innerHeight,window.visualViewport?.height||innerHeight);
    const previewReserve=Math.min(150,Math.max(105,viewport*.38));
    const room=root.getBoundingClientRect().height-globalActions.getBoundingClientRect().height-14-previewReserve;
    const expanded=sidebar.classList.contains('sheet-expanded');
    const cap=Math.min(expanded?Math.min(490,viewport*.46):Math.min(254,viewport*.30),Math.max(chrome+18,room));
    const height=Math.ceil(Math.min(content+chrome,Math.max(chrome+18,cap)));
    const value=height+'px';
    if(sidebar.style.getPropertyValue('--sheet-height')!==value)sidebar.style.setProperty('--sheet-height',value);
    const title=group.getAttribute('aria-label');if(sheetTitle.textContent!==title)sheetTitle.textContent=title;
    sheetToggle.textContent=expanded?'收起 ↓':'展开 ↑';sheetToggle.setAttribute('aria-expanded',String(expanded));
  }
  function scheduleSheet() {
    if(!sheetFrame)sheetFrame=requestAnimationFrame(()=>{sheetFrame=0;refreshView();});
  }
  function syncTextPalette() {
    const select=byId('foregroundTextColor');
    document.querySelectorAll('#foregroundColorDots button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.value===select.value)));
  }
  function mountTextPalette() {
    const select=byId('foregroundTextColor'),old=select.closest('label');
    const field=document.createElement('div');field.className='control foreground-color-field';
    const name=document.createElement('span');name.id='foregroundColorLabel';name.textContent='文字颜色';
    const dots=document.createElement('div');dots.className='color-dots';dots.id='foregroundColorDots';dots.setAttribute('role','group');dots.setAttribute('aria-labelledby',name.id);
    select.hidden=true;old.replaceWith(field);field.append(name,select,dots);
    for(const option of select.options){
      const b=document.createElement('button');b.type='button';b.className='color-dot';b.dataset.value=option.value;
      b.style.setProperty('--swatch',option.value);b.title=option.textContent;b.setAttribute('aria-label',option.textContent+'色');
      b.addEventListener('click',()=>{if(select.value===option.value)return;select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));syncTextPalette();});dots.append(b);
    }
    select.addEventListener('change',syncTextPalette);syncTextPalette();
  }
  function paintOrb(dx=0,dy=0,dragging=false) {
    orb.style.transform=`translate3d(${dx}px,${dy}px,0)`;
    const length=Math.hypot(dx,dy),visible=dragging&&length>1;
    orbOrigin.hidden=orbLine.hidden=!visible;
    orbLine.style.width=length+'px';orbLine.style.transform=`rotate(${Math.atan2(dy,dx)}rad)`;
  }
  function clearMobileSave() {if(mobileSaveURL){URL.revokeObjectURL(mobileSaveURL);mobileSaveURL=null;}}
  async function saveMobilePNG(blob,filename,isCurrent) {
    if(!mobile())return false;
    try {
      const file=new File([blob],filename,{type:'image/png'});
      if(typeof navigator.share==='function'&&typeof navigator.canShare==='function'&&navigator.canShare({files:[file]})){
        await navigator.share({files:[file],title:'IMAGE OBSERVER'});
        return true; // A completed share is not a promise that Photos was selected.
      }
    }catch(error){if(error.name==='AbortError'||!isCurrent())return true;}
    if(!isCurrent())return true;
    // A real full-resolution PNG, not a preview screenshot. Keep explicit links
    // if a browser blocks the new tab or does not offer file sharing.
    clearMobileSave();mobileSaveURL=URL.createObjectURL(blob);
    const status=byId('status'),open=document.createElement('a'),download=document.createElement('a');
    status.dataset.state='save';status.replaceChildren(document.createTextNode('如未出现图片，请'));status.setAttribute('role','status');
    open.href=mobileSaveURL;open.target='_blank';open.rel='noopener';open.textContent='打开 PNG，长按存储图像';
    download.href=mobileSaveURL;download.download=filename;download.textContent='普通下载';
    status.append(open,document.createTextNode(' · '),download);
    globalActions.scrollTop=globalActions.scrollHeight;
    window.open(mobileSaveURL,'_blank','noopener');return true;
  }
  function refreshView() {
    if(!workspace)return;
    const output=byId('output');
    refreshInfo();chooseLayout();
    workspace.classList.toggle('has-image',!output.hidden);
    if(interactionBusy()){viewDeferred=true;return;}
    updateSheet();viewDeferred=false;
    for(const id of ['original','output']) {
      const c=byId(id),preview=c.closest('.preview'),bounds=preview.getBoundingClientRect();
      if(!bounds.width||!bounds.height||c.hidden)continue;
      // clientWidth/clientHeight change when scrollbars appear. Fitting against
      // them feeds the scaled image back into its own layout (125% can oscillate).
      // The allocated border box stays fixed; subtract actual padding/borders
      // and a small rounding allowance, without depending on scrollbar presence.
      const css=getComputedStyle(preview),px=name=>parseFloat(css[name])||0;
      const availableWidth=bounds.width-px('paddingLeft')-px('paddingRight')-px('borderLeftWidth')-px('borderRightWidth')-2;
      const availableHeight=bounds.height-px('paddingTop')-px('paddingBottom')-px('borderTopWidth')-px('borderBottomWidth')-2;
      const heightBudget=availableHeight*(mobile()&&id==='original'?.72:1);
      const fit=Math.min(1,Math.max(1,availableWidth)/c.width,Math.max(1,heightBudget)/c.height);
      const width=Math.max(1,c.width*fit*(mobile()?1:zoom));
      const target=id==='output'?byId('outputStage'):c,value=width+'px';
      if(target.style.width!==value)target.style.width=value;
      if(id==='original')c.style.height='auto';
    }
    zoomLabel.value=`${Math.round((mobile()?1:zoom)*100)}%`;
    paintFocus();
  }
  function scheduleRefresh() {
    if(!resizeFrame)resizeFrame=requestAnimationFrame(()=>{resizeFrame=0;refreshView();});
  }
  function stepZoom(direction) {
    if(mobile())return;
    const stops=[.5,.75,1,1.25,1.5,1.75,2,2.5,3,4].filter(value=>value<=(mobile()?2:4));
    zoom=direction>0?(stops.find(value=>value>zoom+.001)||stops.at(-1)):
      (stops.slice().reverse().find(value=>value<zoom-.001)||stops[0]);
    refreshView();
  }
  function paintFocus() {
    if(!workspace||!controller)return;
    const point=operation?.mode==='focus'?operation.draft:pendingFocus?pendingFocus.draft:controller.info().focus;
    const root=workspace.getBoundingClientRect();
    markers.forEach((marker,index)=>{
      const canvas=byId(index?'output':'original'),r=canvas.getBoundingClientRect(),v=canvas.closest('.preview'),clip=v.getBoundingClientRect();
      const x=point?r.left+point[0]*r.width:0,y=point?r.top+point[1]*r.height:0;
      marker.hidden=!point||canvas.hidden||!r.width||(index&&operation?.mode!=='focus'&&!pendingFocus)||x<clip.left||x>clip.left+v.clientWidth||y<clip.top||y>clip.top+v.clientHeight;
      if(!marker.hidden){marker.style.left=(x-root.left-workspace.clientLeft)+'px';marker.style.top=(y-root.top-workspace.clientTop)+'px';}
    });
  }
  function refreshInteraction() {
    if(!orb||!controller)return;
    refreshInfo();syncTextPalette();scheduleSheet();
    const info=controller.info(),manual=activeGroup===5&&info.editable;
    const box=manual&&info.target==='boxes',fragment=manual&&info.target==='fragments';
    orb.dataset.mode=box?'box':'focus';
    orb.closest('.orb-bar').dataset.mode=orb.dataset.mode;
    orb.disabled=!!pendingFocus||!operation&&(!info.ready||fragment||(box&&!info.selected));
    orb.setAttribute('aria-label',box?'移动识别框':'选择识别焦点');
    orb.title=orb.getAttribute('aria-label');
    orbStatus.title=box&&info.selected?`${info.index+1}/${info.total}`:'';
    orbStatus.textContent=box?(info.selected?'移动框':'选方框'):fragment?'碎片编辑':'选焦点';
    for(const b of [previousBox,nextBox]){b.hidden=!box;b.disabled=!!operation||!!pendingFocus||!info.total;}
    paintFocus();
  }
  function setLocked(value) {
    byId('workbench').classList.toggle('orb-operating',value);
    orb.classList.toggle('active',value);
    const toolbar=workspace.querySelector('.toolbar-lock');
    toolbar.disabled=value;
    if(value){lockedNodes=[byId('parameterWorkspace'),globalActions,panels].map(el=>[el,el.inert]);lockedNodes.forEach(([el])=>el.inert=true);}
    else{lockedNodes.forEach(([el,was])=>el.inert=was);lockedNodes=[];}
  }
  function applyOperation(op) {
    if(operation!==op||!op.pending)return;
    op.pending=false;
    if(op.mode==='focus') {
      const c=byId('output');op.draft=[Math.max(0,Math.min(1-1/c.width,op.origin[0]+op.dx)),Math.max(0,Math.min(1-1/c.height,op.origin[1]+op.dy))];paintFocus();
    } else controller.moveBox(op.token,op.dx,op.dy);
  }
  function releaseOperation(op) {
    try{if(orb.hasPointerCapture(op.id))orb.releasePointerCapture(op.id);}catch(_){/* A canceled native pointer may already be gone. */}
    finally{setLocked(false);paintOrb();refreshInteraction();if(viewDeferred)scheduleSheet();}
  }
  function cancelOperation() {
    if(pendingFocus){const job=pendingFocus;pendingFocus=null;cancelAnimationFrame(job.frame);releaseOperation(job);}
    finishOperation(true);
  }
  function finishOperation(cancel) {
    const op=operation;if(!op)return;
    cancelAnimationFrame(op.frame);
    try {
      if(!cancel)applyOperation(op);
      operation=null;
      if(orb.hasPointerCapture(op.id))orb.releasePointerCapture(op.id);
      if(op.mode==='focus'&&!cancel) {
        // Finish the native gesture before rebuilding canvases/detection. Keep
        // controls locked until this single, cancelable submission has finished.
        pendingFocus=op;
        op.frame=requestAnimationFrame(()=>{
          if(pendingFocus!==op)return;pendingFocus=null;
          try{controller.commitFocus(op.draft);}catch(error){controller.error(error);}finally{releaseOperation(op);}
        });
        refreshInteraction();return;
      }
      if(op.mode==='box')controller.endBox(op.token,cancel);
    }catch(error){if(op.mode==='box')try{controller.endBox(op.token,true);}catch(_){}controller.error(error);}
    operation=null;releaseOperation(op);
  }
  function mount() {
    const main=document.querySelector('main'),header=main.querySelector('header'),intro=main.querySelector('.intro');
    const heading=document.createElement('div');heading.className='heading-copy';header.prepend(heading);heading.append(header.querySelector('h1'),intro);
    intro.textContent='我把房间扫描了一遍，没找到昨晚的声音。Archive_03 未响应';
    main.querySelector('.build').textContent='浏览器本地处理';
    const mark=document.createElementNS('http://www.w3.org/2000/svg','svg');mark.classList.add('brand-mark');mark.setAttribute('viewBox','0 0 64 64');mark.setAttribute('aria-hidden','true');
    mark.innerHTML='<g fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="square"><ellipse cx="32" cy="31" rx="25" ry="12" transform="rotate(-33 32 31)" stroke-dasharray="19 3 11 2 7 3"/></g><circle cx="31" cy="31" r="5" fill="currentColor"/><rect x="45" y="10" width="7" height="6" fill="currentColor"/><rect x="6" y="48" width="6" height="6" fill="currentColor"/>';
    header.prepend(mark);
    const root=document.createElement('div');root.id='workbench';main.append(root);
    sidebar=document.createElement('aside');sidebar.id='parameterWorkspace';sidebar.setAttribute('aria-label','参数工作区');root.append(sidebar);
    const global=document.createElement('div');global.className='global-actions';sidebar.append(global);globalActions=global;
    const upload=byId('dropZone');upload.querySelector('strong').textContent='上传图片';global.append(upload,byId('randomEffects'));
    const hint=Array.from(main.querySelectorAll('span.edit-hint')).find(e=>e.textContent.includes('手动碎片'));if(hint)global.append(hint);
    main.querySelector('.preset-area summary').prepend(icon('M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z'));
    global.append(main.querySelector('.preset-area'),byId('status'));
    byId('editTarget').value='boxes';
    const dragHint=document.createElement('p');dragHint.className='edit-hint drag-hint';dragHint.textContent='可直接拖动方框^_^';
    const fragmentParams=byId('fragmentParams');fragmentParams.insertBefore(byId('fragmentCount').closest('label'),byId('fragmentHue').closest('label'));
    const navigation=document.createElement('nav');navigation.className='function-navigation';navigation.setAttribute('aria-label','功能导航');sidebar.append(navigation);
    const scroll=document.createElement('div');scroll.id='parameterScroll';sidebar.append(scroll);parameterScroll=scroll;
    sheetHeader=document.createElement('div');sheetHeader.className='mobile-sheet-header';
    sheetTitle=document.createElement('strong');sheetToggle=document.createElement('button');sheetToggle.type='button';sheetToggle.id='mobileExpand';
    sheetToggle.setAttribute('aria-controls','parameterScroll');sheetToggle.onclick=()=>{sidebar.classList.toggle('sheet-expanded');scheduleSheet();};
    sheetHeader.append(sheetTitle,sheetToggle);sidebar.insertBefore(sheetHeader,navigation);
    const groups=[
      ['识别与标注','M4 4h6M4 4v6m16-6h-6m6 0v6M4 20h6m-6 0v-6m16 6h-6m6 0v-6',[
        byId('structure').closest('label'),byId('strokeWidth').closest('.controls'),byId('customTextField'),byId('distortionControl'),dragHint,byId('resetFocus')]],
      ['底图滤镜','M4 6h16M7 12h10M10 18h4',[
        byId('baseFilter').closest('.controls'),byId('originalControls'),byId('xrayInvert').closest('label'),byId('xrayControls'),byId('baseContrast').closest('label'),byId('vignette').closest('label')]],
      ['效果层','m12 3 10 5-10 5L2 8l10-5zm-10 9 10 5 10-5M2 17l10 5 10-5',[byId('effect1').closest('.effect-layers')]],
      ['图像碎片奔逸','M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm12 1h6v6h-6z',[byId('fragmentOn').closest('section')]],
      ['前景文字奔逸','M4 5h16M12 5v15m-5 0h10',[byId('foregroundTextOn').closest('section')]],
      ['手动编辑','m4 16 12-12 4 4L8 20H4v-4zm10-10 4 4',[byId('editBoxes').closest('.edit-controls'),byId('editHint')]]
    ];
    const tabs=[],sections=[];
    groups.forEach(([name,path,nodes],index)=>{
      const section=document.createElement('section');section.className='parameter-group';section.id='parameterGroup'+index;section.hidden=index!==0;section.setAttribute('aria-label',name);
      const h=document.createElement('h2');h.dataset.index=String(index+1).padStart(2,'0');h.textContent=name;section.append(h,...nodes);scroll.append(section);sections.push(section);
      const tab=button('functionTab'+index,name,path,()=>{
        activeGroup=index;
        sections.forEach((s,i)=>s.hidden=i!==index);tabs.forEach((t,i)=>{t.classList.toggle('selected',i===index);t.setAttribute('aria-pressed',String(i===index));});scroll.scrollTop=0;
        refreshInteraction();scheduleSheet();tab.scrollIntoView({block:'nearest',inline:'nearest'});
      });tab.dataset.index=String(index+1).padStart(2,'0');tab.dataset.short=['标注','底图','效果','碎片','文字','编辑'][index];
      const full=document.createElement('span');full.className='function-name';full.textContent=name;tab.lastChild.replaceWith(full);
      tab.classList.toggle('selected',index===0);tab.setAttribute('aria-pressed',String(index===0));tab.setAttribute('aria-controls',section.id);navigation.append(tab);tabs.push(tab);
    });
    mountTextPalette();
    workspace=document.createElement('section');workspace.id='canvasWorkspace';workspace.setAttribute('aria-label','实时画布工作区');root.append(workspace);
    const workspaceHead=document.createElement('div');workspaceHead.className='workspace-heading';
    const workspaceTitle=document.createElement('strong');workspaceTitle.textContent='实时工作区';
    const layoutInfo=document.createElement('span');layoutInfo.id='layoutInfo';layoutInfo.textContent='左右对照';workspaceHead.append(workspaceTitle,layoutInfo);workspace.append(workspaceHead);
    const toolbar=document.createElement('div');toolbar.className='canvas-toolbar';workspace.append(toolbar);
    toolbar.append(button('undoAction','撤销','M9 4 3 10l6 6M3 10h11a6 6 0 0 1 6 6'),button('redoAction','重做','m15 4 6 6-6 6m6-6H10a6 6 0 0 0-6 6'));
    byId('downloadPNG').prepend(icon('M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5'));toolbar.append(byId('downloadPNG'));
    toolbar.append(button('zoomOut','缩小','M5 12h14',()=>stepZoom(-1)));
    zoomLabel=document.createElement('output');zoomLabel.id='canvasZoomValue';zoomLabel.setAttribute('aria-label','画布缩放');toolbar.append(zoomLabel);
    toolbar.append(button('zoomIn','放大','M5 12h14M12 5v14',()=>stepZoom(1)),button('fitCanvas','适应视图','M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6',()=>{zoom=1;refreshView();}));
    const expand=button('expandCanvas','放大查看','M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6',()=>{workspace.classList.remove('collapsed');workspace.classList.toggle('expanded');expand.lastChild.textContent=workspace.classList.contains('expanded')?'退出放大':'放大查看';refreshView();});toolbar.append(expand);
    const toolbarLock=document.createElement('fieldset');toolbarLock.className='toolbar-lock';toolbarLock.append(...toolbar.childNodes);toolbar.append(toolbarLock);
    // Native mobile click synthesis can be dropped after pointer capture/locking.
    // Activate an unmoved touch once at release; ignore only its later ghost click.
    let buttonTouch=null,ghostClick=null;
    root.addEventListener('pointerdown',event=>{
      buttonTouch=null;const target=event.target.closest('button');
      if(event.pointerType==='touch'&&target&&target.id!=='mobileOrb'&&!target.matches(':disabled')&&!operation&&!pendingFocus)
        buttonTouch={target,id:event.pointerId,x:event.clientX,y:event.clientY};
    });
    root.addEventListener('pointercancel',()=>{buttonTouch=null;});
    root.addEventListener('pointerup',event=>{
      const touch=buttonTouch;buttonTouch=null;
      if(!touch||touch.id!==event.pointerId||touch.target!==event.target.closest('button')||
        touch.target.matches(':disabled')||operation||pendingFocus||Math.hypot(event.clientX-touch.x,event.clientY-touch.y)>8)return;
      ghostClick={target:touch.target,time:performance.now()};touch.target.click();
    });
    root.addEventListener('click',event=>{
      if(event.isTrusted&&event.detail>0&&ghostClick&&event.target.closest('button')===ghostClick.target&&
        performance.now()-ghostClick.time<700&&(event.pointerType!=='mouse'||event.sourceCapabilities?.firesTouchEvents))event.stopImmediatePropagation();
    },true);
    byId('fitCanvas').className='desktop-only';expand.className='desktop-only';
    panels=main.querySelector('.panels');panels.dataset.layout='side';workspace.append(panels);
    [['originalLabel','原图','CLICK TO FOCUS','source'],['outputLabel','实时输出','ARCHIVE / 03','output']].forEach(([id,label,helper,prefix])=>{
      const title=byId(id),primary=document.createElement('span'),secondary=document.createElement('span');
      primary.className='pane-title';primary.textContent=label;secondary.className='pane-helper';secondary.textContent=helper;title.replaceChildren(primary,secondary);
      const info=document.createElement('div');info.className='image-info';
      for(const [suffix,name] of [['FileName','pane-file'],['Dimensions','pane-dimensions'],['State','pane-state']]){const node=document.createElement('span');node.id=prefix+suffix;node.className=name;info.append(node);}
      title.closest('.panel').append(info);
    });
    for(const id of ['zoomOut','zoomIn','canvasZoomValue'])byId(id).classList.add('desktop-only');
    markers=['original','output'].map(id=>{const marker=document.createElement('span');marker.className='focus-crosshair';marker.id=id+'FocusMarker';marker.hidden=true;marker.setAttribute('aria-hidden','true');workspace.append(marker);return marker;});
    const orbBar=document.createElement('div');orbBar.className='orb-bar';orbBar.setAttribute('aria-label','手机精确操控');
    orbStatus=document.createElement('span');orbStatus.id='orbStatus';orbStatus.setAttribute('role','status');
    previousBox=button('previousBox','上一识别框','m14 5-7 7 7 7',()=>controller?.selectBox(-1));
    nextBox=button('nextBox','下一识别框','m10 5 7 7-7 7',()=>controller?.selectBox(1));
    orb=button('mobileOrb','选择识别焦点','M12 4v16M4 12h16');orb.disabled=true;
    orb.lastChild.remove(); // Keep the accessible label; the visible orb contains only +.
    const dock=document.createElement('span');dock.className='orb-dock';
    orbOrigin=document.createElement('span');orbOrigin.className='orb-origin';orbOrigin.hidden=true;
    orbLine=document.createElement('span');orbLine.className='orb-line';orbLine.hidden=true;
    for(const node of [orbOrigin,orbLine])node.setAttribute('aria-hidden','true');
    dock.append(orbOrigin,orbLine,orb);
    const orbHint=document.createElement('span');orbHint.className='orb-hint';orbHint.textContent='拖动右侧触控球试试吖^^';
    orbBar.append(orbStatus,previousBox,orbHint,dock,nextBox);workspace.append(orbBar);
    orb.addEventListener('pointerdown',event=>{
      if(!mobile()||orb.disabled||operation||event.isPrimary===false||event.button!==0)return;
      event.preventDefault();const info=controller.info(),mode=orb.dataset.mode;
      try {
        const token=mode==='box'?controller.beginBox():null;
        if(mode==='box'&&!token)return;
        if(mode==='focus')controller.beginFocus();
        const rect=byId('output').getBoundingClientRect();if(!rect.width||!rect.height)return;
        operation={mode,token,id:event.pointerId,x:event.clientX,y:event.clientY,width:rect.width,height:rect.height,
          origin:info.focus||[.5,.5],draft:info.focus||[.5,.5],dx:0,dy:0,frame:0,pending:false};
        setLocked(true);orb.setPointerCapture(event.pointerId);refreshInteraction();
      }catch(error){finishOperation(true);controller.error(error);}
    });
    orb.addEventListener('pointermove',event=>{
      const op=operation;if(!op||event.pointerId!==op.id)return;
      event.preventDefault();op.dx=(event.clientX-op.x)/op.width;op.dy=(event.clientY-op.y)/op.height;op.pending=true;
      paintOrb(event.clientX-op.x,event.clientY-op.y,true);
      if(!op.frame)op.frame=requestAnimationFrame(()=>{op.frame=0;applyOperation(op);});
    });
    orb.addEventListener('pointerup',event=>{if(operation?.id===event.pointerId)finishOperation(false);});
    orb.addEventListener('pointercancel',event=>{if(operation?.id===event.pointerId)finishOperation(true);});
    orb.addEventListener('lostpointercapture',event=>{layoutPointers.delete(event.pointerId);if(operation?.id===event.pointerId)finishOperation(true);scheduleSheet();});
    orb.addEventListener('contextmenu',event=>event.preventDefault());
    window.addEventListener('blur',()=>{layoutPointers.clear();cancelOperation();scheduleSheet();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden){layoutPointers.clear();cancelOperation();scheduleSheet();}});
    panels.addEventListener('scroll',scheduleRefresh,{capture:true,passive:true});
    window.addEventListener('resize',()=>{cancelOperation();if(mobile()){zoom=1;workspace.classList.remove('expanded');}scheduleRefresh();});
    window.visualViewport?.addEventListener('resize',()=>{cancelOperation();scheduleRefresh();});
    // Freeze layout for all in-progress pointer gestures (including sliders and
    // direct frame/fragment drags); resume only after their end handlers finish.
    root.addEventListener('pointerdown',event=>{if(mobile())layoutPointers.add(event.pointerId);},true);
    const endLayoutGesture=event=>{layoutPointers.delete(event.pointerId);scheduleSheet();};
    window.addEventListener('pointerup',endLayoutGesture);window.addEventListener('pointercancel',endLayoutGesture);
    window.addEventListener('pagehide',event=>{if(!event.persisted)clearMobileSave();});
    // Empty old wrappers have no role after moving their existing child nodes.
    for(const node of Array.from(main.children))if(!['HEADER'].includes(node.tagName)&&node!==root)node.remove();
    // Scrollbar/content changes must not schedule another fitting pass.
    previewObserver=new ResizeObserver(scheduleRefresh);panels.querySelectorAll('.preview').forEach(node=>previewObserver.observe(node,{box:'border-box'}));
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&workspace.classList.contains('expanded')){workspace.classList.remove('expanded');expand.lastChild.textContent='放大查看';refreshView();}});
    sheetObserver=new ResizeObserver(scheduleSheet);
    sections.forEach(section=>sheetObserver.observe(section,{box:'border-box'}));
    sheetObserver.observe(globalActions,{box:'border-box'});
    new MutationObserver(scheduleSheet).observe(scroll,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden']});
    refreshView();
  }
  return Object.freeze({mount,refreshView,refreshInteraction,saveMobilePNG,isOperating:()=>!!operation||!!pendingFocus,
    cancelOperation,setController:api=>{controller=api;refreshInteraction();}});
})();
ObserverWorkbench.mount();
