/* DOM-only workbench: retains original control nodes, handlers and canvas pixels. */
window.ObserverWorkbench = (()=>{
  const byId=id=>document.getElementById(id);
  let zoom=1,workspace,panels,zoomLabel,previewObserver,resizeFrame=0,focusHandler=null;
  const mobile=()=>matchMedia('(max-width:820px), (pointer:coarse) and (max-width:1100px)').matches;
  function icon(path) {const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('width','16');s.setAttribute('height','16');s.setAttribute('fill','none');s.setAttribute('stroke','currentColor');s.setAttribute('stroke-width','1.6');s.setAttribute('aria-hidden','true');const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',path);s.append(p);return s;}
  function button(id,text,path,action) {const b=document.createElement('button');b.id=id;b.type='button';b.title=text;b.setAttribute('aria-label',text);b.append(icon(path),document.createTextNode(text));if(action)b.onclick=action;return b;}
  function refreshView() {
    if(!workspace)return;
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
      const fit=Math.min(1,Math.max(1,availableWidth)/c.width,Math.max(1,availableHeight)/c.height);
      const width=Math.max(1,c.width*fit*zoom);
      const target=id==='output'?byId('outputStage'):c,value=width+'px';
      if(target.style.width!==value)target.style.width=value;
      if(id==='original')c.style.height='auto';
    }
    zoomLabel.value=`${Math.round(zoom*100)}%`;
  }
  function scheduleRefresh() {
    if(!resizeFrame)resizeFrame=requestAnimationFrame(()=>{resizeFrame=0;refreshView();});
  }
  function stepZoom(direction) {
    const stops=[.5,.75,1,1.25,1.5,1.75,2,2.5,3,4].filter(value=>value<=(mobile()?2:4));
    zoom=direction>0?(stops.find(value=>value>zoom+.001)||stops.at(-1)):
      (stops.slice().reverse().find(value=>value<zoom-.001)||stops[0]);
    refreshView();
  }
  function mount() {
    const main=document.querySelector('main'),header=main.querySelector('header'),intro=main.querySelector('.intro');
    const heading=document.createElement('div');heading.className='heading-copy';header.prepend(heading);heading.append(header.querySelector('h1'),intro);
    intro.textContent='我把房间扫描了一遍，没找到昨晚的声音。Archive_03 未响应';
    main.querySelector('.build').textContent='浏览器本地处理';
    const root=document.createElement('div');root.id='workbench';main.append(root);
    const sidebar=document.createElement('aside');sidebar.id='parameterWorkspace';sidebar.setAttribute('aria-label','参数工作区');root.append(sidebar);
    const global=document.createElement('div');global.className='global-actions';sidebar.append(global);
    const upload=byId('dropZone');upload.querySelector('strong').textContent='上传图片';global.append(upload,byId('randomEffects'));
    const hint=Array.from(main.querySelectorAll('span.edit-hint')).find(e=>e.textContent.includes('手动碎片'));if(hint)global.append(hint);
    main.querySelector('.preset-area summary').prepend(icon('M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z'));
    global.append(main.querySelector('.preset-area'),byId('status'));
    byId('editTarget').value='boxes';
    const dragHint=document.createElement('p');dragHint.className='edit-hint';dragHint.textContent='可直接拖动方框^_^';
    const fragmentParams=byId('fragmentParams');fragmentParams.insertBefore(byId('fragmentCount').closest('label'),byId('fragmentHue').closest('label'));
    const navigation=document.createElement('nav');navigation.className='function-navigation';navigation.setAttribute('aria-label','功能导航');sidebar.append(navigation);
    const scroll=document.createElement('div');scroll.id='parameterScroll';sidebar.append(scroll);
    const groups=[
      ['识别与标注','M4 4h6M4 4v6m16-6h-6m6 0v6M4 20h6m-6 0v-6m16 6h-6m6 0v-6',[
        byId('structure').closest('label'),byId('strokeWidth').closest('.controls'),byId('customTextField'),byId('distortionControl'),dragHint,byId('resetFocus')]],
      ['底图滤镜','M4 6h16M7 12h10M10 18h4',[
        byId('baseFilter').closest('.controls'),byId('xrayInvert').closest('label'),byId('xrayControls'),byId('baseContrast').closest('label'),byId('vignette').closest('label')]],
      ['效果层','m12 3 10 5-10 5L2 8l10-5zm-10 9 10 5 10-5M2 17l10 5 10-5',[byId('effect1').closest('.effect-layers')]],
      ['图像碎片奔逸','M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm12 1h6v6h-6z',[byId('fragmentOn').closest('section')]],
      ['前景文字奔逸','M4 5h16M12 5v15m-5 0h10',[byId('foregroundTextOn').closest('section')]],
      ['手动编辑','m4 16 12-12 4 4L8 20H4v-4zm10-10 4 4',[byId('editBoxes').closest('.edit-controls'),byId('editHint')]]
    ];
    const tabs=[],sections=[];
    groups.forEach(([name,path,nodes],index)=>{
      const section=document.createElement('section');section.className='parameter-group';section.id='parameterGroup'+index;section.hidden=index!==0;section.setAttribute('aria-label',name);
      const h=document.createElement('h2');h.textContent=name;section.append(h,...nodes);scroll.append(section);sections.push(section);
      const tab=button('functionTab'+index,name,path,()=>{
        sections.forEach((s,i)=>s.hidden=i!==index);tabs.forEach((t,i)=>{t.classList.toggle('selected',i===index);t.setAttribute('aria-pressed',String(i===index));});scroll.scrollTop=0;
        tab.scrollIntoView({block:'nearest',inline:'nearest'});
      });tab.classList.toggle('selected',index===0);tab.setAttribute('aria-pressed',String(index===0));tab.setAttribute('aria-controls',section.id);navigation.append(tab);tabs.push(tab);
    });
    workspace=document.createElement('section');workspace.id='canvasWorkspace';workspace.setAttribute('aria-label','实时画布工作区');workspace.dataset.mobileView='output';root.append(workspace);
    const toolbar=document.createElement('div');toolbar.className='canvas-toolbar';workspace.append(toolbar);
    toolbar.append(button('undoAction','撤销','M9 4 3 10l6 6M3 10h11a6 6 0 0 1 6 6'),button('redoAction','重做','m15 4 6 6-6 6m6-6H10a6 6 0 0 0-6 6'));
    byId('downloadPNG').prepend(icon('M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5'));toolbar.append(byId('downloadPNG'));
    toolbar.append(button('zoomOut','缩小','M5 12h14',()=>stepZoom(-1)));
    zoomLabel=document.createElement('output');zoomLabel.id='canvasZoomValue';zoomLabel.setAttribute('aria-label','画布缩放');toolbar.append(zoomLabel);
    toolbar.append(button('zoomIn','放大','M5 12h14M12 5v14',()=>stepZoom(1)),button('fitCanvas','适应视图','M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6',()=>{zoom=1;refreshView();}));
    const expand=button('expandCanvas','放大查看','M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6',()=>{workspace.classList.remove('collapsed');workspace.classList.toggle('expanded');expand.lastChild.textContent=workspace.classList.contains('expanded')?'退出放大':'放大查看';refreshView();});toolbar.append(expand);
    byId('fitCanvas').className='desktop-only';expand.className='desktop-only';
    panels=main.querySelector('.panels');workspace.append(panels);byId('outputLabel').textContent='实时输出';
    const holdHint=document.createElement('p');holdHint.className='hold-hint';holdHint.textContent='按住预览查看原图 · 关闭编辑后轻点设焦点';workspace.insertBefore(holdHint,panels);
    let holdTimer=null,press=null,holdConsumed=false;
    const stopHold=()=>{clearTimeout(holdTimer);holdTimer=null;press=null;workspace.classList.remove('holding-original');};
    panels.addEventListener('pointerdown',event=>{
      if(!mobile()||event.isPrimary===false||event.button!==0||byId('output').hidden)return;
      stopHold();holdConsumed=false;press={id:event.pointerId,x:event.clientX,y:event.clientY};
      holdTimer=setTimeout(()=>{if(press){holdConsumed=true;workspace.classList.add('holding-original');refreshView();const views=panels.querySelectorAll('.preview');views[0].scrollLeft=views[1].scrollLeft;views[0].scrollTop=views[1].scrollTop;}},260);
    },true);
    document.addEventListener('pointermove',event=>{if(press&&event.pointerId===press.id&&Math.hypot(event.clientX-press.x,event.clientY-press.y)>6)stopHold();},true);
    for(const type of ['pointerup','pointercancel','lostpointercapture'])document.addEventListener(type,stopHold,true);
    window.addEventListener('blur',stopHold);document.addEventListener('visibilitychange',()=>{if(document.hidden)stopHold();});
    panels.addEventListener('click',event=>{
      if(!mobile()||!focusHandler)return;
      if(holdConsumed){holdConsumed=false;return;}
      if(byId('editBoxes').value!=='Off')return;
      const canvas=byId('output'),r=canvas.getBoundingClientRect();
      if(!r.width||event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)return;
      focusHandler([(event.clientX-r.left)*canvas.width/r.width,(event.clientY-r.top)*canvas.height/r.height]);
    });
    panels.addEventListener('contextmenu',event=>{if(mobile())event.preventDefault();});
    window.addEventListener('resize',()=>{stopHold();if(mobile()){zoom=Math.min(zoom,2);workspace.classList.remove('expanded');}scheduleRefresh();});
    // Empty old wrappers have no role after moving their existing child nodes.
    for(const node of Array.from(main.children))if(!['HEADER'].includes(node.tagName)&&node!==root)node.remove();
    // Scrollbar/content changes must not schedule another fitting pass.
    previewObserver=new ResizeObserver(scheduleRefresh);panels.querySelectorAll('.preview').forEach(node=>previewObserver.observe(node,{box:'border-box'}));
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&workspace.classList.contains('expanded')){workspace.classList.remove('expanded');expand.lastChild.textContent='放大查看';refreshView();}});
    refreshView();
  }
  return Object.freeze({mount,refreshView,setFocusHandler:handler=>focusHandler=handler});
})();
ObserverWorkbench.mount();
