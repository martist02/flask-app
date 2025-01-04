fetch('https://your-backend-host.com/api/user')
.then(response => response.json())
.then(data => {
  document.getElementById('name').textContent = data.name;
  document.getElementById('relative_name').textContent = data.relative_name;
  document.getElementById('relative_phone').textContent = data.relative_phone;
  document.getElementById('medical_condition').textContent = data.medical_condition;
});
