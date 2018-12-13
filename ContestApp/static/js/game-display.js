$(document).ready(function(){
    var gameSocket = new WebSocket('ws://192.168.0.172:80/ws/gamemaster/');
    $("#containerCategories").hide();
    $("#containerQuestion").hide();
    $("#containerInfo").hide();

    let intervalID = 0;

    gameSocket.onmessage = function(event) {
        let msg = JSON.parse(event.data);
        switch(msg.type){
            case "send.categories":
                clearInterval(intervalID);
                $("#containerCategories").show();
                $("#containerQuestion").hide();
                $("#containerInfo").hide();
                let categories = msg.categories;
                let team = msg.team;
                $("#teamName").text(team);
                let idx = 1;
                for (let key in categories){
                    let categoryContainer = $("#categ" + idx.toString());
                    categoryContainer.removeClass();
                    categoryContainer.addClass('col category');
                    if (categories[key] == true){
                        categoryContainer.addClass('category-normal');
                    } else {
                        categoryContainer.addClass('category-disabled');
                    }
                    idx ++;
                    let child = categoryContainer.children(".category-name")[0];
                    child.innerText = key;
                }
                $("#firstTeamScore").text(msg.first_team_name + ": " + msg.first_team_score);
                $("#secondTeamScore").text(msg.second_team_score + ": " + msg.second_team_name );
                break;
            case "category.receive":
                clearInterval(intervalID);
                let category = msg.category;
                // Find the container
                let categoryContainer = $(".category-name:contains('" + category + "')");
                categoryContainer.parent().removeClass('category-normal').addClass('category-selected');
                break;
            case "send.question":
                clearInterval(intervalID);
                $("#containerQuestion").show();
                $("#containerCategories").hide();
                $("#containerInfo").hide();

                let text = msg.question_text;
                $("#questionText").text(text);

                let answers = msg.answers;

                for (let key in answers){
                    let answerContainer = $("#answer" + key.toString());
                    answerContainer.removeClass();
                    answerContainer.addClass('col answer answer-normal');
                    answerContainer.children('.answer-text')[0].innerText = answers[key];
                }
                break;
            case "answer.receive":
                clearInterval(intervalID);
                let receivedAnswer = msg.answer;
                let answerContainer = $("#answer" + receivedAnswer.toString());
                answerContainer.addClass('col answer answer-selected');
                break;
            case "answer.reveal":
                clearInterval(intervalID);
                let correctAnswer = msg.answer;
                let correctAnswerContainer = $("#answer" + correctAnswer.toString());
                let originalClasses = correctAnswerContainer.attr('class');
                intervalID = setInterval(function(correctAnswerContainer, originalClasses){
                    correctAnswerContainer.removeClass();
                    correctAnswerContainer.addClass("col answer answer-correct")
                    setTimeout(function(container, theClass){
                        correctAnswerContainer.removeClass();
                        correctAnswerContainer.addClass(theClass);
                    }, 500, correctAnswerContainer, originalClasses);
                }, 1100, correctAnswerContainer, originalClasses);
                break;
            case "ranking":
                clearInterval(intervalID);
                $("#containerQuestion").hide();
                $("#containerCategories").hide();
                $("#containerInfo").show();
                if (msg.first_team_score > msg.second_team_score){
                    $("#winningTeamName").text(msg.first_team_name);
                    $("#winningTeamPoints").text(msg.first_team_score);
                    $("#loserTeamName").text(msg.second_team_name);
                    $("#loserTeamPoints").text(msg.second_team_score);
                } else {
                    $("#winningTeamName").text(msg.second_team_name);
                    $("#winningTeamPoints").text(msg.second_team_score);
                    $("#loserTeamName").text(msg.first_team_name);
                    $("#loserTeamPoints").text(msg.first_team_score);
                }
                break;

        }

    }
});