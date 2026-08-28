function showTime() {
	document.getElementById('currentTime').innerHTML = new Date().toUTCString();
}

function copyScript() {
  const scriptText = document.getElementById('scriptText').innerText;
  navigator.clipboard.writeText(scriptText).then(() => {
    const btn = document.querySelector('.copy-btn');
    btn.innerText = 'Copied!';
    setTimeout(() => {
      btn.innerText = 'Copy Script';
    }, 2000);
  });
}

// Show current time
showTime();
setInterval(function () {
	showTime();
}, 1000);
