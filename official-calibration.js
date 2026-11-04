/* Official recipes and temporary local calibration. No repository write access.
   Reuses the personal-template validators, thumbnails and recipe application path. */
window.ObserverOfficialCalibration = (() => {
  'use strict';
  const FORMAT='image-observer-official-preset',VERSION=1;
  const plain=value=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
  function init(api) {
    const config=window.ObserverOfficialPresets,container=document.getElementById('officialCards');
    const panel=document.getElementById('officialDeveloper'),status=document.getElementById('officialStatus');
    const slot=document.getElementById('officialSlot'),name=document.getElementById('officialName'),values=document.getElementById('officialValues'),file=document.getElementById('officialFile');
    const defaults=new Map(),overrides=new Map();let dbPromise,busy=false,revision=0;
    const say=(text,error=false)=>{status.textContent=text;status.style.color=error?'#b42c34':'';};
    const descriptionOf=value=>{if(typeof value!=='string'||Array.from(value).length>160)throw new Error('预设说明格式不正确。');return value;};
    function header(input) {
      if(!plain(input)||input.version!==VERSION||!/^official-0[1-4]$/.test(input.id))throw new Error('官方预设槽位或版本不正确。');
      return {id:input.id,version:VERSION,name:api.nameOf(input.name),description:descriptionOf(input.description??''),params:api.validateRecipe(input.params)};
    }
    function staticRecord(input) {
      const record=header(input),url=new URL(input.thumbnail,location.href),root=new URL('assets/presets/',location.href);
      if(typeof input.thumbnail!=='string'||url.origin!==root.origin||!url.pathname.startsWith(root.pathname)||!(/\.(jpg|jpeg|png|webp)$/i.test(url.pathname))||url.search||url.hash)throw new Error('官方缩略图须为预设目录中的静态图片。');
      return {...record,thumbnail:url.href};
    }
    // Calibration and personal templates deliberately use separate databases.
    function database() {
      if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{
        if(!window.indexedDB){reject(new Error('浏览器不支持本地校准存储。'));return;}
        let request;try{request=indexedDB.open('image-observer-official-calibration',1);}catch(error){reject(error);return;}
        request.onupgradeneeded=()=>request.result.createObjectStore('overrides',{keyPath:'id'});
        request.onerror=()=>reject(request.error||new Error('无法打开本地校准存储。'));
        request.onblocked=()=>reject(new Error('校准存储被其他页面占用，请关闭其他页面后重试。'));
        request.onsuccess=()=>{request.result.onversionchange=()=>request.result.close();resolve(request.result);};
      });
      return dbPromise;
    }
    async function transaction(mode,operation) {
      const db=await database();return new Promise((resolve,reject)=>{
        let tx,request;try{tx=db.transaction('overrides',mode);request=operation(tx.objectStore('overrides'));}catch(error){reject(error);return;}
        tx.oncomplete=()=>resolve(request.result);
        tx.onerror=tx.onabort=()=>reject(tx.error||request.error||new Error('校准保存失败。'));
      });
    }
    const current=id=>overrides.get(id)||defaults.get(id);
    function selection() {const record=current(slot.value);if(!record)throw new Error('请先选择官方预设。');return record;}
    function showSelection() {
      const record=selection();name.value=record.name;
      document.getElementById('officialSource').textContent=overrides.has(record.id)?'当前为本浏览器的校准覆盖值，尚未写回网站静态配置。':'当前为随网站发布的初始官方预设。';
    }
    async function refresh() {
      const token=++revision,nodes=[];
      for(const id of defaults.keys()) {
        const record=current(id),node=await api.card({name:record.name,recipe:record.params,thumbnail:record.thumbnail});
        node.classList.add('official-card');node.dataset.presetId=id;
        if(record.description){const p=document.createElement('p');p.className='preset-caption';p.textContent=record.description;node.append(p);}
        if(overrides.has(id)){const p=document.createElement('small');p.textContent='本地校准';node.append(p);}
        nodes.push(node);
      }
      if(token!==revision)return;container.replaceChildren(...nodes);
      for(const option of slot.options)option.textContent=current(option.value).name;
      showSelection();
    }
    function lock(locked) {busy=locked;panel.querySelectorAll('button,select,input').forEach(el=>el.disabled=locked);}
    const act=fn=>async()=>{
      if(busy)return;lock(true);
      try{await fn();}catch(error){say(`操作失败：${error.message||'请重试。'}`,true);}finally{lock(false);}
    };
    async function persist(record) {
      // Only publish to in-memory cards after the disk transaction succeeds.
      await transaction('readwrite',store=>store.put(record));overrides.set(record.id,record);await refresh();
    }
    async function dataThumbnail(record) {
      if(record.thumbnail.startsWith('data:')){await api.validateThumbnail(record.thumbnail);return record.thumbnail;}
      const image=new Image();image.src=record.thumbnail;
      try{await image.decode();}catch(_){throw new Error('静态缩略图加载失败，请用当前输出更新缩略图后重试。');}
      return api.blobURL(await api.thumbnail(image));
    }
    const capture=()=>api.validateRecipe(api.capture());
    const currentThumbnail=async()=>api.blobURL(await api.thumbnail(api.canvas()));
    slot.onchange=()=>{showSelection();values.value='';};
    document.getElementById('readOfficialParams').onclick=act(async()=>{values.value=JSON.stringify(api.capture(),null,2);say('已读取当前控件与视觉随机状态；不含图片或检测框。上传图片后初始化情绪词状态。');});
    document.getElementById('saveOfficial').onclick=act(async()=>{
      // Capture controls and bitmap in the same turn, before JPEG compression
      // yields: edits elsewhere in the workbench must not mix two states.
      const record=selection(),canvas=api.canvas(),params=capture(),presetName=api.nameOf(name.value);
      const next={...record,name:presetName,params,thumbnail:await api.blobURL(await api.thumbnail(canvas))};
      await persist(next);values.value=JSON.stringify(next.params,null,2);say('已保存参数、名称和真实缩略图，仅保存在本浏览器。当前工作图像未改变。');
    });
    document.getElementById('renameOfficial').onclick=act(async()=>{
      const record=selection();await persist({...record,name:api.nameOf(name.value)});say('已在本浏览器保存名称。');
    });
    document.getElementById('updateOfficialThumbnail').onclick=act(async()=>{
      const record=selection();await persist({...record,thumbnail:await currentThumbnail()});say('已更新本地预览缩略图；预设参数保持不变。');
    });
    document.getElementById('exportOfficial').onclick=act(async()=>{
      const record=selection(),preset={...record,thumbnail:await dataThumbnail(record)};
      api.download({format:FORMAT,version:VERSION,preset},`image-observer-${record.id}.json`);say('已导出本槽位 JSON，含参数、随机状态和压缩缩略图。尚未写回 GitHub。');
    });
    document.getElementById('importOfficial').onclick=()=>{if(!busy){file.value='';file.click();}};
    file.onchange=act(async()=>{
      const input=file.files[0],target=slot.value;if(!input)return;
      if(input.size>240000)throw new Error('官方预设 JSON 文件过大。');
      let data;try{data=JSON.parse(await input.text());}catch(_){throw new Error('无法解析官方预设 JSON。');}
      if(!plain(data)||data.format!==FORMAT||data.version!==VERSION)throw new Error('不是支持的官方预设文件；个人模板请使用“导入模板”。');
      const parsed=header(data.preset);await api.validateThumbnail(data.preset.thumbnail);
      await persist({...parsed,id:target,thumbnail:data.preset.thumbnail});values.value=JSON.stringify(parsed.params,null,2);say('已导入所选槽位，仅覆盖本浏览器校准值；当前图像未改变。');
    });
    document.getElementById('resetOfficial').onclick=act(async()=>{
      const id=selection().id;if(!confirm('清除此槽位的本地校准，恢复网站初始值？当前图像不会改变。'))return;
      await transaction('readwrite',store=>store.delete(id));overrides.delete(id);await refresh();values.value='';say('已恢复本轮初始官方预设。');
    });
    async function start() {
      if(!config||config.version!==VERSION||!Array.isArray(config.slots)||config.slots.length!==4)throw new Error('官方预设配置须包含四个槽位。');
      for(const input of config.slots){const record=staticRecord(input);if(defaults.has(record.id))throw new Error('官方预设槽位重复。');defaults.set(record.id,record);const option=document.createElement('option');option.value=record.id;option.textContent=`官方预设 ${record.id.slice(-2)}`;slot.append(option);}
      await refresh();
      try {
        const saved=await transaction('readonly',store=>store.getAll());let invalid=0;
        for(const input of saved)try{const record=header(input);if(input.thumbnail?.startsWith('data:'))await api.validateThumbnail(input.thumbnail);else staticRecord(input);overrides.set(record.id,{...record,thumbnail:input.thumbnail});}catch(_){invalid++;}
        await refresh();say(invalid?'部分本地校准数据损坏，已跳过；对应槽位仍使用静态初始值。':'本地校准仅影响本浏览器；导出 JSON 可备份或提交审核。',!!invalid);
      } catch(error){say(`本地校准存储不可用：${error.message}；静态官方预设仍可应用。`,true);}
    }
    lock(true);start().catch(error=>say(error.message,true)).finally(()=>lock(false));
  }
  return Object.freeze({init});
})();
