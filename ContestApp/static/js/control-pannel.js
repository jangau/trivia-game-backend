$(document).ready(function() {
    let connection;
    $("#btnConnect").click(function(){
        connection = new WebSocket('ws://192.168.0.105:80/ws/gamemaster/');
        connection.onmessage = function(event) {
            let msg = JSON.parse(event.data);
            $("#datalog").append("<br>" + event.data);
        }
        $("#dataLog").append("<br>Connected!");
    })
    $("#btnContinue").click(function(){
        let data = {
            type: "duel_game_continue",
            game: $("#gameID").val()
        }
        connection.send(JSON.stringify(data));
        $("#dataLog").append("<br>Sent: " + JSON.stringify(data));
    });
   $("#btnReveal").click(function(){
        let data = {
            type: "reveal_answer",
            game: $("#gameID").val()
        }
        connection.send(JSON.stringify(data));
        $("#dataLog").append("<br>Sent: " + JSON.stringify(data));
    });
});