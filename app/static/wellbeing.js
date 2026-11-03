'use strict';
let age='25-34', domain='nutrients', lifeStage='';
const ageButtons=document.querySelectorAll('[data-age]');
const domainButtons=document.querySelectorAll('[data-domain]');
const status=document.getElementById('wellbeing-status');
const papers=document.getElementById('wellbeing-papers');
function make(tag,content,cls){const e=document.createElement(tag);if(content!==undefined)e.textContent=content;if(cls)e.className=cls;return e;}
async function update(){
 const params=new URLSearchParams({age,domain,life_stage:lifeStage});
 status.textContent='Retrieving recent PubMed research…';
 papers.replaceChildren();
 const term={nutrients:'vitamins minerals dietary intake',exercise:'physical activity strength training',sleep:'sleep quality duration',prevention:'preventive health screening'}; 
 const query=[term[domain],'women',age,lifeStage].filter(Boolean).join(' ');
 for(const d of Object.keys(term)){
   const a=document.getElementById('research-'+d);
   a.href='https://pubmed.ncbi.nlm.nih.gov/?term='+encodeURIComponent([term[d],'women',age,lifeStage].filter(Boolean).join(' '));
 }
 try{
   const r=await fetch('/api/wellbeing/literature?'+params);
   if(!r.ok)throw new Error('Research is temporarily unavailable. Please try again.');
   const data=await r.json();
   status.textContent=data.items.length ? data.items.length+' recent publications · Broad age-group keyword search · Retrieved '+new Date(data.retrieved_at).toLocaleDateString() : 'No publications returned for this combination. Try a broader filter.';
   for(const item of data.items){
     const card=make('article',undefined,'paper-card');
     card.append(make('span',[item.published,item.journal].filter(Boolean).join(' · '),'paper-meta'));
     const link=make('a',item.title+' ↗');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';
     card.append(link,make('p',item.authors.join(', ')));papers.append(card);
   }
 }catch(err){status.textContent=err.message;}
}
ageButtons.forEach(b=>b.addEventListener('click',()=>{age=b.dataset.age.replace('–','-');ageButtons.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));update();}));
domainButtons.forEach(b=>b.addEventListener('click',()=>{domain=b.dataset.domain;domainButtons.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));update();}));
document.getElementById('life-stage').addEventListener('change',e=>{lifeStage=e.target.value;update();});
update();
