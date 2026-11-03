/* Bounded, bitmap-free state history. Rendering and image ownership stay in app. */
window.ObserverHistory = Object.freeze({create({capture,restore,onChange,limit=30}) {
  let states=[],index=-1;
  const clone=value=>JSON.parse(JSON.stringify(value));
  const notify=()=>onChange({canUndo:index>0,canRedo:index>=0&&index<states.length-1,steps:Math.max(0,states.length-1)});
  function reset() {const state=capture();states=state?[clone(state)]:[];index=states.length-1;notify();}
  function clear() {states=[];index=-1;notify();}
  function commit() {
    const state=capture();if(!state)return;
    const text=JSON.stringify(state);if(index>=0&&JSON.stringify(states[index])===text)return;
    states=states.slice(0,index+1);states.push(clone(state));
    if(states.length>limit+1)states.shift();index=states.length-1;notify();
  }
  function travel(delta) {const next=index+delta;if(next<0||next>=states.length)return;restore(clone(states[next]));index=next;notify();}
  clear();return Object.freeze({reset,clear,commit,undo:()=>travel(-1),redo:()=>travel(1)});
}});
