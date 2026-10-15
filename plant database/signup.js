//for the signup form

const supabaseClient = window.supabase.createClient(
  'https://vfewattbwlfuxdcozouz.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmZXdhdHRid2xmdXhkY296b3V6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5MDk3MTYsImV4cCI6MjEwNzQ4NTcxNn0.vauaMzbxjwVi4VTA55TT6MtD7GM4hznt9ftIoyN3G2Q'
);

const signupForm = document.getElementById('signup-form');
const signupMessage = document.getElementById('signup-message');

signupForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const btn = signupForm.querySelector('button');
  btn.disabled = true;
  signupMessage.textContent = 'Creating account...';

  const { error } = await supabaseClient.auth.signUp({
    email: document.getElementById('email').value,
    password: document.getElementById('new-password').value,
    options: {
      data: {
        full_name: document.getElementById('fullname').value,
        username: document.getElementById('new-username').value
      }
    }
  });

  if (error) {
    console.error(error);
    signupMessage.textContent = error.message;
    btn.disabled = false;
  } else {
    window.location.href = 'welcome.html';
  }
b });