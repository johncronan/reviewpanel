
function show(refId, itemId) {
  let id = 'itemref_' + refId + '_' + itemId;
  let itemRef = document.getElementById(id);
  let section = itemRef.parentElement;
  section.querySelectorAll('.item-reference')
         .forEach(r => {
    if (r.dataset.ref == refId) r.style.display = 'none';
  });
  itemRef.style.display = 'flex';
}

function selectorClick(event) {
  let item = event.currentTarget;
  let selector = item.parentElement.parentElement;
  
  let refs = selector.dataset.refs.split(' ');
  for (let i=0; i < refs.length; i++) show(refs[i], item.dataset.id);
}

document.querySelectorAll('.item-thumbnail')
        .forEach(thumb => thumb.onclick = selectorClick);

function showModal(event) {
  let img = event.target;
  let modal = document.getElementById('modal');
  let target = modal.querySelector('img');
  modal.style.display = 'block';
  target.src = img.src;
}

document.querySelectorAll('img.item_image')
        .forEach(img => img.onclick = showModal);

document.querySelector('img.modal-content').onclick = (event) => {
  document.getElementById('modal').style.display = 'none';
};

function overflowState(scrollPos, content) {
  let parent = content.parentElement;
  let width = parent.clientWidth;
  
  var show = '', hide = '', pos = Math.ceil(scrollPos);
  if (pos && content.clientWidth - pos > width) show = '.thumb-advance';
  else if (pos) {
    show = '.thumb-advance-left';
    hide = '.thumb-advance-right';
  } else if (content.clientWidth - pos > width) {
    show = '.thumb-advance-right';
    hide = '.thumb-advance-left';
  } else hide = '.thumb-advance';
  
  if (show) parent.parentElement.querySelectorAll(show).forEach(btn => {
    btn.style.opacity = 1;
  });
  if (hide) parent.parentElement.querySelectorAll(hide).forEach(btn => {
    btn.style.opacity = 0;
  });
}

var state = {};

function advanceScroll(event) {
  let btn = event.currentTarget.parentElement;
  let dir = btn.classList.contains('thumb-advance-right');
  let selector = btn.parentElement.firstElementChild;
  let thumbs = selector.firstElementChild;
  let scrollPos = state[selector.parentElement.id].lastPos;
  let n = (dir ? 1 : -1) * Math.floor(selector.clientWidth / 150);
  selector.scrollTo({'left': scrollPos + n*150, 'behavior': 'smooth'});
}

document.querySelectorAll('.advancer-icon')
        .forEach(icon => icon.onclick = advanceScroll);

document.querySelectorAll('.item-selector-section')
        .forEach(section => {
  state[section.id] = { lastPos: 0, ticking: false }
});

document.querySelectorAll('.item-selector')
        .forEach(selector => {
  selector.addEventListener('scroll', function(event) {
    let sel = event.target, sec = sel.parentElement;
    state[sec.id].lastPos = sel.scrollLeft;
    if (!state[sec.id].ticking) {
      window.requestAnimationFrame(function() {
        overflowState(state[sec.id].lastPos, sel.firstElementChild);
        state[sec.id].ticking = false;
      });
    }
    state[sec.id].ticking = true;
  });
});

window.onresize = function () {
  for (const section in state) {
    let selector = document.getElementById(section).firstElementChild;
    overflowState(state[section].lastPos, selector.firstElementChild);
  }
}
window.onresize();

var timer = 0;
if (document.querySelector('div.inputs'))
  timer = parseInt(document.querySelector('div.inputs').dataset.minSecs);

function disableForm(input) {
  input.value = timer;
  input.setAttribute('disabled', 'disabled');
}
function enableForm(input) {
  input.value = '\u2192';
  input.removeAttribute('disabled');
}

function scoreChange(event) {
  if (!timer) return;
  let input = document.querySelector('input[name="next"]');
  if (document.querySelector('input.primary-input').value) disableForm(input);
  else enableForm(input);
}

if (timer) {
  document.querySelector('input.primary-input').oninput = scoreChange;
  (function dec() {
    let input = document.querySelector('input[name="next"]');
    if (timer <= 0) return enableForm(input);
    if (document.querySelector('input.primary-input').value) disableForm(input);
    else enableForm(input);
    timer -= 1;
    setTimeout(dec, 1000);
  })();
}
