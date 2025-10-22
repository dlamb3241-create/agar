const cardPaths = ['img/card1.jpg','img/card2.jpg','img/card3.jpg','img/card4.jpg'];
const themes = [{brand:'#dc2626'},{brand:'#0ea5e9'},{brand:'#10b981'},{brand:'#f59e0b'}];
let idx=0;
function applyTheme(i){
  const t=themes[i%themes.length];
  document.body.style.setProperty('--brand', t.brand);
  const ann=document.getElementById('announce'); if(ann) ann.style.background=t.brand;
  document.querySelectorAll('.btn-primary').forEach(b=>{b.style.background=t.brand;b.style.borderColor=t.brand;});
}
function rotateCard(){
  const img=document.getElementById('rotating-card'); if(!img) return;
  idx=(idx+1)%cardPaths.length; img.src='/static/'+cardPaths[idx]; applyTheme(idx);
}
setInterval(rotateCard, 3000); applyTheme(0);
