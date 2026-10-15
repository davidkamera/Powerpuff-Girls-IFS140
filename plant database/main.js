// Image gallery functionality
const slides = document.querySelectorAll('.gallery figure');
const nextBtn = document.getElementById('next');
let current = 0;

nextBtn.addEventListener('click', () => {
  slides[current].classList.remove('active');
  current = (current + 1) % slides.length;
  slides[current].classList.add('active');
});

// Login form handling

const loginForm = document.getElementById('login-form');
const message = document.getElementById('login-message');

const supabaseClient = window.supabase.createClient('https://vfewattbwlfuxdcozouz.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmZXdhdHRid2xmdXhkY296b3V6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5MDk3MTYsImV4cCI6MjEwNzQ4NTcxNn0.vauaMzbxjwVi4VTA55TT6MtD7GM4hznt9ftIoyN3G2Q');

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const { error } = await supabaseClient.auth.signInWithPassword({
    email: document.getElementById('username').value, // Supabase logs in by email
    password: document.getElementById('password').value
  });
  if (error) message.textContent = error.message;
  else window.location.href = 'dashboard.html';
});
